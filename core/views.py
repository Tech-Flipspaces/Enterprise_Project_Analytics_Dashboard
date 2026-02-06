import pandas as pd
from datetime import datetime, timedelta
from io import BytesIO
from django.shortcuts import render, redirect       # type:ignore
from django.contrib import messages                 # type:ignore
from django.http import HttpResponse                # type:ignore
from django.db.models import Q                      # type:ignore

from .forms import UploadFileForm
from .models import Project
from .constants import METRICS_CONFIG, EXCEL_COL_MAP

# ==============================================================================
#  INTERNAL HELPER FUNCTIONS (The Engine Room)
#  These functions handle the logic shared across all views.
# ==============================================================================

def _get_request_params(request):
    """
    Extracts and normalizes standard parameters (Dates, View Mode, Filters) from the request.
    Returns calculated date objects including the 'Rolling Window' for execution stats.
    """
    default_start = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    default_end = datetime.now().strftime('%Y-%m-%d')
    
    view_mode = request.GET.get('view', 'Sales')
    start_str = request.GET.get('start', default_start)
    end_str = request.GET.get('end', default_end)
    sbu_filter = request.GET.getlist('sbu') or ['North', 'South', 'West', 'Central']
    role_filter = request.GET.get('metric_role', 'All Roles')

    try:
        start_dt = datetime.strptime(start_str, '%Y-%m-%d').date()
        end_dt = datetime.strptime(end_str, '%Y-%m-%d').date()
    except ValueError:
        start_dt = datetime.now().date() - timedelta(days=30)
        end_dt = datetime.now().date()

    # Streamlit Logic: Rolling Window (6 months back, 8 months forward)
    roll_start = start_dt - timedelta(days=180)
    roll_end = end_dt + timedelta(days=240)

    return view_mode, start_str, end_str, start_dt, end_dt, sbu_filter, role_filter, roll_start, roll_end

def _apply_people_filters(queryset, view_mode, request):
    """
    Applies the specific people filters (Head, Lead, PM, etc.) based on the View Mode.
    """
    def _filter(qs, db_field, get_param):
        selected = request.GET.getlist(get_param)
        if not selected: return qs
        q = Q()
        for name in selected: q |= Q(**{f"{db_field}__icontains": name})
        return qs.filter(q)

    if view_mode == 'Sales':
        queryset = _filter(queryset, 'sales_head', 'f_s_head')
        queryset = _filter(queryset, 'sales_lead', 'f_s_lead')
    elif view_mode == 'Design':
        queryset = _filter(queryset, 'design_dh', 'f_d_dh')
        queryset = _filter(queryset, 'design_dm', 'f_d_dm')
        queryset = _filter(queryset, 'design_id', 'f_d_id')
        queryset = _filter(queryset, 'design_3d', 'f_d_3d')
    elif view_mode == 'Operations':
        queryset = _filter(queryset, 'ops_head', 'f_o_head')
        queryset = _filter(queryset, 'ops_pm', 'f_o_pm')
        queryset = _filter(queryset, 'ops_om', 'f_o_om')
        queryset = _filter(queryset, 'ops_ss', 'f_o_ss')
        queryset = _filter(queryset, 'ops_mep', 'f_o_mep')
        queryset = _filter(queryset, 'ops_csc', 'f_o_csc')
    
    return queryset

def _get_stage_querysets(view_mode, projects, start_dt, end_dt, roll_start, roll_end):
    """
    Splits the main project list into 'Pre-Stage' and 'Post-Stage' querysets
    based on the specific business rules for Sales, Design, and Ops.
    """
    # Common Rolling Window Mask (Intersection Logic)
    q_rolling = Q(start_date__gte=roll_start) & Q(start_date__lte=end_dt) & \
                Q(end_date__gte=start_dt) & Q(end_date__lte=roll_end)

    qs_pre = Project.objects.none()
    qs_post = Project.objects.none()

    if view_mode == 'Sales':
        # Pre: Login Date | Post: Rolling + Stage Check
        qs_pre = projects.filter(login_date__gte=start_dt, login_date__lte=end_dt, stage='Pre Sales')
        qs_post = projects.filter(q_rolling, stage='Post Sales')

    elif view_mode == 'Design':
        # Pre: Login Date | Post: Rolling
        qs_pre = projects.filter(login_date__gte=start_dt, login_date__lte=end_dt)
        qs_post = projects.filter(q_rolling).distinct()

    elif view_mode == 'Operations':
        # Pre: None | Post: Rolling
        qs_post = projects.filter(q_rolling).distinct()

    return qs_pre, qs_post

def _get_dropdown_context(request):
    """
    Generates the context for all dropdown filters (Options list + Selected status).
    """
    def get_opts(field):
        try:
            vals = Project.objects.values_list(field, flat=True).distinct()
            return sorted([v for v in vals if v and str(v).strip()])
        except: return []

    people_opts = {
        's_head': get_opts('sales_head'), 's_lead': get_opts('sales_lead'),
        'd_dh': get_opts('design_dh'), 'd_dm': get_opts('design_dm'),
        'd_id': get_opts('design_id'), 'd_3d': get_opts('design_3d'),
        'o_head': get_opts('ops_head'), 'o_pm': get_opts('ops_pm'),
        'o_om': get_opts('ops_om'), 'o_ss': get_opts('ops_ss'),
        'o_mep': get_opts('ops_mep'), 'o_csc': get_opts('ops_csc'),
    }
    
    selected_filters = {
        's_head': request.GET.getlist('f_s_head'), 's_lead': request.GET.getlist('f_s_lead'),
        'd_dh': request.GET.getlist('f_d_dh'), 'd_dm': request.GET.getlist('f_d_dm'),
        'd_id': request.GET.getlist('f_d_id'), 'd_3d': request.GET.getlist('f_d_3d'),
        'o_head': request.GET.getlist('f_o_head'), 'o_pm': request.GET.getlist('f_o_pm'),
        'o_om': request.GET.getlist('f_o_om'), 'o_ss': request.GET.getlist('f_o_ss'),
        'o_mep': request.GET.getlist('f_o_mep'), 'o_csc': request.GET.getlist('f_o_csc'),
    }
    return people_opts, selected_filters


# ==============================================================================
# 1. UPLOAD VIEW
# ==============================================================================
def upload_view(request):
    if request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                # --- Excel Parsing Logic (Kept intact) ---
                file = request.FILES['file']
                xls = pd.ExcelFile(file)
                sheet_map = {'sales': '', 'design': '', 'operation': ''}
                for name in xls.sheet_names:
                    lower = str(name).lower()
                    if 'sales' in lower: sheet_map['sales'] = str(name)
                    elif 'design' in lower: sheet_map['design'] = str(name)
                    elif 'operation' in lower or 'ops' in lower: sheet_map['operation'] = str(name)

                project_data_map = {}

                # Helpers
                def clean_str(val): return '' if pd.isnull(val) or str(val).strip().lower() == 'nan' else str(val).strip()
                def parse_date(val): return pd.to_datetime(val).date() if pd.notnull(val) else None
                def clean_num(val):
                    if pd.isnull(val): return 0.0
                    try: return float(str(val).replace('%','').replace(',','').strip())
                    except: return 0.0
                def get_clean_id(row):
                    for c in ['Project Code','project_code','Code','code','Lead Id']:
                        if c in row.index and pd.notnull(row[c]):
                            v = str(row[c]).strip().upper()
                            if v and v != 'NAN': return v.replace('.0','')
                    return None

                def process_sheet(sheet_name, sheet_type):
                    if not sheet_name: return
                    df = pd.read_excel(file, sheet_name=sheet_name)
                    df.columns = [str(c).strip() for c in df.columns]

                    # Custom Maths
                    if sheet_type == 'design':
                        if 'No Key Plans Spaces' in df.columns and 'Mapped Spaces' in df.columns:
                            df['Key Plans Ratio'] = pd.to_numeric(df['No Key Plans Spaces'], errors='coerce').fillna(0) / pd.to_numeric(df['Mapped Spaces'], errors='coerce').replace(0,1).fillna(0)
                        if 'Layouts' in df.columns and 'Furniture Layouts' in df.columns:
                            df['Other Layouts'] = df['Layouts'] - df['Furniture Layouts']
                    
                    if sheet_type == 'operation':
                        ops_calcs = [('WPR Half Week','WPR Download Weeks','Weeks Till Date'), ('Manpower Ratio','Actual Manpower','Planned Manpower'),
                                     ('DPR Ratio','DPR Added Days','Days Till Date'), ('Manpower Day Ratio','Manpower Added Days','Days Till Date')]
                        for t, n, d in ops_calcs:
                            if n in df.columns and d in df.columns:
                                df[t] = (pd.to_numeric(df[n], errors='coerce') / pd.to_numeric(df[d], errors='coerce').replace(0,1)).fillna(0)

                    # Row Mapping
                    for _, row in df.iterrows():
                        p_id = get_clean_id(row)
                        if not p_id: continue
                        if p_id not in project_data_map: project_data_map[p_id] = {'project_code': p_id}
                        
                        # Meta Data
                        meta = {
                            'project_name': ['Project Name'], 'sbu': ['SBU'], 'stage': ['Stage', 'Status'],
                            'sales_head': ['Sales Head'], 'sales_lead': ['Sales Lead'],
                            'design_dh': ['Design Head', 'DH'], 'design_dm': ['Design Lead', 'DM'], 'design_id': ['Design ID', 'ID'], 'design_3d': ['3D Visualizer', '3D'],
                            'ops_head': ['Ops Head'], 'ops_pm': ['Project Manager', 'SPM/PM'], 'ops_om': ['Ops Manager', 'SOM/OM'], 'ops_ss': ['Site Supervisor', 'SS'],
                            'ops_mep': ['MEP'], 'ops_csc': ['CSC']
                        }
                        for db, opts in meta.items():
                            for col in opts:
                                if col in row.index: 
                                    v = clean_str(row[col])
                                    if v: project_data_map[p_id][db] = v
                                    break
                        
                        # Dates
                        dates = {'login_date': ['Project Login Date'], 'start_date': ['Project Start Date'], 'end_date': ['Project End Date']}
                        for db, opts in dates.items():
                            for col in opts:
                                if col in row.index: 
                                    v = parse_date(row[col])
                                    if v: project_data_map[p_id][db] = v
                                    break

                        # Metrics
                        full_map = EXCEL_COL_MAP.copy()
                        full_map.update({'Key Plans Ratio':'key_plans_ratio', 'Other Layouts':'other_layouts', 'WPR Half Week':'wpr_half_week',
                                         'Manpower Ratio':'manpower_ratio', 'DPR Ratio':'dpr_ratio', 'Manpower Day Ratio':'manpower_day_ratio'})
                        for xl, db in full_map.items():
                            if xl in row.index:
                                v = clean_num(row[xl])
                                if v != 0 or db not in project_data_map[p_id]: project_data_map[p_id][db] = v

                process_sheet(sheet_map['sales'], 'sales')
                process_sheet(sheet_map['design'], 'design')
                process_sheet(sheet_map['operation'], 'operation')

                Project.objects.all().delete()
                Project.objects.bulk_create([Project(**d) for d in project_data_map.values()])
                messages.success(request, f"Successfully uploaded {len(project_data_map)} projects.")
                return redirect('dashboard')

            except Exception as e:
                messages.error(request, f"Upload Failed: {str(e)}")
    else:
        form = UploadFileForm()
    return render(request, 'core/upload.html', {'form': form})


# ==============================================================================
# 2. DASHBOARD VIEW (Refactored)
# ==============================================================================
def dashboard_view(request):
    # 1. Fetch Request Params & Context
    view_mode, start_str, end_str, start_dt, end_dt, sbu_filter, role_filter, roll_start, roll_end = _get_request_params(request)
    people_opts, selected_filters = _get_dropdown_context(request)

    # 2. Filter Projects
    projects = Project.objects.filter(sbu__in=sbu_filter)
    projects = _apply_people_filters(projects, view_mode, request)

    # 3. Split into Stages
    qs_pre, qs_post = _get_stage_querysets(view_mode, projects, start_dt, end_dt, roll_start, roll_end)
    
    pre_count = qs_pre.count()
    post_count = qs_post.count()

    # 4. Metric Calculation Engine (Specific for Dashboard Cards)
    def calculate_card_metrics(queryset, metrics, prefix):
        results_prim, results_sec = [], []
        for m in metrics:
            # A. Dynamic Priority: If role selected, match=Primary, no-match=Secondary
            is_primary = True
            if role_filter != "All Roles":
                is_primary = role_filter in m.get('roles', [])

            # B. Threshold
            param_name = f"thresh_{prefix}_{m['field']}"
            user_input = request.GET.get(param_name)
            try: threshold = float(user_input) if user_input else m['def']
            except: threshold = m['def']

            # C. Data & List
            filtered_qs = queryset.filter(**{f"{m['field']}__gte": threshold})
            count = filtered_qs.count()
            proj_names = list(filtered_qs.values_list('project_name', flat=True).order_by('project_name'))

            item = {'label': m['label'], 'param': param_name, 'threshold': threshold, 'count': count, 'field': m['field'], 'project_list': proj_names}
            
            if is_primary: results_prim.append(item)
            else: results_sec.append(item)
        return results_prim, results_sec

    # 5. Execute Calculations
    pre_prim, pre_sec = [], []
    if view_mode != 'Operations':
        pre_prim, pre_sec = calculate_card_metrics(qs_pre, METRICS_CONFIG[view_mode]['Pre'], 'pre')
    
    post_prim, post_sec = [], []
    post_metrics = METRICS_CONFIG[view_mode] if view_mode == 'Operations' else METRICS_CONFIG[view_mode]['Post']
    post_prim, post_sec = calculate_card_metrics(qs_post, post_metrics, 'post')

    # 6. Render
    sbu_opts = sorted([s for s in Project.objects.values_list('sbu', flat=True).distinct() if s])
    
    context = {
        'view_mode': view_mode, 'start_date': start_str, 'end_date': end_str,
        'sbus': sbu_opts or ['North', 'South', 'West', 'Central'], 'selected_sbus': sbu_filter,
        'current_role': role_filter, 'people_opts': people_opts, 'selected_filters': selected_filters,
        'pre_prim': pre_prim, 'pre_sec': pre_sec, 'pre_count': pre_count,
        'post_prim': post_prim, 'post_sec': post_sec, 'post_count': post_count,
    }
    return render(request, 'core/dashboard.html', context)


# ==============================================================================
# 3. EXPORT SUMMARY VIEW (Excel)
# ==============================================================================
def export_view(request):
    # 1. Reuse Common Logic
    view_mode, _, _, start_dt, end_dt, sbu_filter, role_filter, roll_start, roll_end = _get_request_params(request)
    projects = Project.objects.filter(sbu__in=sbu_filter)
    projects = _apply_people_filters(projects, view_mode, request)
    qs_pre, qs_post = _get_stage_querysets(view_mode, projects, start_dt, end_dt, roll_start, roll_end)

    # 2. DataFrame Generator
    def generate_summary_df(queryset, metrics, prefix):
        total = queryset.count()
        data = [{"Metric Name": "TOTAL PROJECTS", "Threshold": "-", "Value": total, "%": "-"}]
        
        for m in metrics:
            # Export Rule: If specific role selected, EXCLUDE non-matching metrics entirely.
            if role_filter != "All Roles" and role_filter not in m.get('roles', []): continue

            param_name = f"thresh_{prefix}_{m['field']}"
            user_input = request.GET.get(param_name)
            try: threshold = float(user_input) if user_input else m['def']
            except: threshold = m['def']
            
            count = queryset.filter(**{f"{m['field']}__gte": threshold}).count()
            pct = round((count / total * 100), 1) if total > 0 else 0.0
            data.append({"Metric Name": m['label'], "Threshold": threshold, "Value": count, "%": f"{pct}%"})
        
        return pd.DataFrame(data)

    # 3. Build & Write
    df_pre = generate_summary_df(qs_pre, METRICS_CONFIG[view_mode]['Pre'], 'pre') if view_mode != 'Operations' else pd.DataFrame()
    
    post_metrics = METRICS_CONFIG[view_mode] if view_mode == 'Operations' else METRICS_CONFIG[view_mode]['Post']
    df_post = generate_summary_df(qs_post, post_metrics, 'post')

    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        if not df_pre.empty: df_pre.to_excel(writer, sheet_name='Pre-Stage', index=False)
        if not df_post.empty: df_post.to_excel(writer, sheet_name='Post-Stage', index=False)
        if df_pre.empty and df_post.empty: pd.DataFrame({'Info': ['No Data']}).to_excel(writer, sheet_name='Empty', index=False)

    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="Summary_{view_mode}.xlsx"'
    return response


# ==============================================================================
# 4. EXPORT DETAILED VIEW (Excel)
# ==============================================================================
def export_detailed_view(request):
    # 1. Reuse Common Logic
    view_mode, _, _, start_dt, end_dt, sbu_filter, role_filter, roll_start, roll_end = _get_request_params(request)
    projects = Project.objects.filter(sbu__in=sbu_filter)
    projects = _apply_people_filters(projects, view_mode, request)
    qs_pre, qs_post = _get_stage_querysets(view_mode, projects, start_dt, end_dt, roll_start, roll_end)

    # 2. Detailed Data Generator
    def generate_detailed_df(queryset, metrics):
        active_metrics = [m for m in metrics if role_filter == "All Roles" or role_filter in m.get('roles', [])]
        if not active_metrics: return pd.DataFrame()

        db_fields = [m['field'] for m in active_metrics]
        data = list(queryset.values('project_name', *db_fields))
        if not data: return pd.DataFrame()

        df = pd.DataFrame(data)
        rename_map = {'project_name': 'Project Name'}
        for m in active_metrics: rename_map[m['field']] = m['label']
        df = df.rename(columns=rename_map).fillna(0)

        sum_row = df.sum(numeric_only=True)
        sum_row['Project Name'] = 'Grand Total'
        return pd.concat([df, sum_row.to_frame().T], ignore_index=True)

    # 3. Build & Write
    df_pre = generate_detailed_df(qs_pre, METRICS_CONFIG[view_mode]['Pre']) if view_mode != 'Operations' else pd.DataFrame()
    
    post_metrics = METRICS_CONFIG[view_mode] if view_mode == 'Operations' else METRICS_CONFIG[view_mode]['Post']
    df_post = generate_detailed_df(qs_post, post_metrics)

    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        if not df_pre.empty: df_pre.to_excel(writer, sheet_name='Pre-Detailed', index=False)
        if not df_post.empty: df_post.to_excel(writer, sheet_name='Post-Detailed', index=False)
        if df_pre.empty and df_post.empty: pd.DataFrame({'Info': ['No Data']}).to_excel(writer, sheet_name='Empty', index=False)

    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="Detailed_{view_mode}.xlsx"'
    return response


# ==============================================================================
# 5. LIVE REPORT DETAILED (HTML)
# ==============================================================================
def report_detailed_view(request):
    # 1. Reuse Common Logic
    view_mode, start_str, end_str, start_dt, end_dt, sbu_filter, role_filter, roll_start, roll_end = _get_request_params(request)
    projects = Project.objects.filter(sbu__in=sbu_filter)
    projects = _apply_people_filters(projects, view_mode, request)
    qs_pre, qs_post = _get_stage_querysets(view_mode, projects, start_dt, end_dt, roll_start, roll_end)

    # 2. Logic duplicated from export_detailed_view (required for context rendering)
    def generate_detailed_df(queryset, metrics):
        active_metrics = [m for m in metrics if role_filter == "All Roles" or role_filter in m.get('roles', [])]
        if not active_metrics: return pd.DataFrame()
        
        db_fields = [m['field'] for m in active_metrics]
        data = list(queryset.values('project_name', *db_fields))
        if not data: return pd.DataFrame()

        df = pd.DataFrame(data)
        rename_map = {'project_name': 'Project Name'}
        for m in active_metrics: rename_map[m['field']] = m['label']
        df = df.rename(columns=rename_map).fillna(0)
        
        sum_row = df.sum(numeric_only=True)
        sum_row['Project Name'] = 'Grand Total'
        return pd.concat([df, sum_row.to_frame().T], ignore_index=True)

    df_pre = generate_detailed_df(qs_pre, METRICS_CONFIG[view_mode]['Pre']) if view_mode != 'Operations' else pd.DataFrame()
    
    post_metrics = METRICS_CONFIG[view_mode] if view_mode == 'Operations' else METRICS_CONFIG[view_mode]['Post']
    df_post = generate_detailed_df(qs_post, post_metrics)

    context = {
        'view_mode': view_mode, 'start_date': start_str, 'end_date': end_str,
        'df_pre': df_pre.to_html(classes='table table-bordered table-striped table-hover table-sm', index=False, justify='center') if not df_pre.empty else None,
        'df_post': df_post.to_html(classes='table table-bordered table-striped table-hover table-sm', index=False, justify='center') if not df_post.empty else None,
    }
    return render(request, 'core/report_detailed.html', context)

def report_view(request):
    return redirect('dashboard')