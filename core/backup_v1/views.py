import pandas as pd
import uuid
from datetime import datetime, timedelta

from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import HttpResponse
from django.db.models import Q

from .forms import UploadFileForm
from .models import Project
from .constants import METRICS_CONFIG, EXCEL_COL_MAP

# ==========================================
# 1. UPLOAD VIEW (With Merge Inspector)
# ==========================================
def upload_view(request):
    if request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)
        
        if form.is_valid():
            file = request.FILES['file']
            try:
                xls = pd.ExcelFile(file)
                
                # 1. DEFINE SHEET MAP
                sheet_map: dict = {'sales': None, 'design': None, 'operation': None}
                for name in xls.sheet_names:
                    lower_name = str(name).lower()
                    if 'sales' in lower_name: sheet_map['sales'] = name
                    elif 'design' in lower_name: sheet_map['design'] = name
                    elif 'operation' in lower_name or 'ops' in lower_name: sheet_map['operation'] = name

                # 2. MASTER DICTIONARY
                project_data_map = {}

                # --- HELPER FUNCTIONS ---
                def clean_str(val):
                    if pd.isnull(val): return ''
                    s = str(val).strip()
                    return '' if s.lower() == 'nan' else s

                def parse_date(val):
                    if pd.isnull(val): return None
                    try: return pd.to_datetime(val).date()
                    except: return None

                def clean_num(val):
                    if pd.isnull(val): return 0.0
                    if isinstance(val, str):
                        clean_val = val.replace('%', '').replace(',', '').strip()
                        if clean_val == '' or clean_val.lower() == 'nan' or '#' in clean_val:
                            return 0.0
                        try: return float(clean_val)
                        except: return 0.0
                    try: return float(val)
                    except: return 0.0

                def get_clean_id(row):
                    for col in ['Project Code', 'project_code', 'Code', 'code', 'Lead Id', 'Lead ID']:
                        if col in row.index and pd.notnull(row[col]):
                            val = str(row[col]).strip().upper()
                            if val and val != 'NAN':
                                return val.replace('.0', '') 
                    return None

                # --- PROCESS FUNCTION ---
                def process_sheet(sheet_name, sheet_type):
                    if not sheet_name: return
                    
                    df = pd.read_excel(file, sheet_name=sheet_name)
                    df.columns = [str(c).strip() for c in df.columns] 
                    
                    if sheet_type == 'design':
                        if 'No Key Plans Spaces' in df.columns and 'Mapped Spaces' in df.columns:
                            num = pd.to_numeric(df['No Key Plans Spaces'], errors='coerce').fillna(0)
                            den = pd.to_numeric(df['Mapped Spaces'], errors='coerce').fillna(0)
                            df['Key Plans Ratio'] = num / den.replace(0, 1)

                        if 'Layouts' in df.columns and 'Furniture Layouts' in df.columns:
                            df['Other Layouts'] = df['Layouts'] - df['Furniture Layouts']

                    if sheet_type == 'operation':
                        calcs = [
                            ('WPR Half Week',      'WPR Download Weeks',   'Weeks Till Date'),
                            ('Manpower Ratio',     'Actual Manpower',      'Planned Manpower'),
                            ('DPR Ratio',          'DPR Added Days',       'Days Till Date'),
                            ('Manpower Day Ratio', 'Manpower Added Days',  'Days Till Date')
                        ]
                        for target, num_col, den_col in calcs:
                            if num_col in df.columns and den_col in df.columns:
                                num = pd.to_numeric(df[num_col], errors='coerce').fillna(0)
                                den = pd.to_numeric(df[den_col], errors='coerce').fillna(0)
                                df[target] = (num / den.replace(0, 1)).fillna(0)
                    
                    # ADD TO MASTER DICTIONARY
                    for _, row in df.iterrows():
                        p_id = get_clean_id(row)
                        if not p_id: continue 

                        if p_id not in project_data_map:
                            project_data_map[p_id] = {'project_code': p_id}

                        meta_map = {
                            'project_name': ['Project Name', 'project_name'],
                            'sbu': ['SBU', 'sbu'],
                            'stage': ['Stage', 'stage', 'Status'],
                            'sales_head': ['Sales Head', 'sales_head'],
                            'sales_lead': ['Sales Lead', 'sales_lead'],
                            'design_dh': ['Design Head', 'DH', 'design_dh'],
                            'design_dm': ['Design Lead', 'DM', 'design_dm'],
                            'design_id': ['Design ID', 'ID', 'design_id'],
                            'design_3d': ['3D Visualizer', '3D', 'design_3d'],
                            'ops_head': ['Ops Head', 'Cluster/BU Head', 'ops_head'],
                            'ops_pm': ['Project Manager', 'SPM/PM', 'ops_pm'],
                            'ops_om': ['Ops Manager', 'SOM/OM', 'ops_om'],
                            'ops_ss': ['Site Supervisor', 'SS', 'ops_ss'],
                        }
                        
                        for db_field, excel_candidates in meta_map.items():
                            for col in excel_candidates:
                                if col in row.index:
                                    val = clean_str(row[col])
                                    if val: 
                                        project_data_map[p_id][db_field] = val
                                    break

                        date_map = {
                            'login_date': ['Project Login Date', 'Login Date', 'project_login_date'],
                            'start_date': ['Project Start Date', 'Start Date', 'project_start_date'],
                            'end_date':   ['Project End Date', 'End Date', 'project_end_date']
                        }
                        for db_field, excel_candidates in date_map.items():
                            for col in excel_candidates:
                                if col in row.index:
                                    val = parse_date(row[col])
                                    if val: 
                                        project_data_map[p_id][db_field] = val
                                    break

                        local_map = EXCEL_COL_MAP.copy()
                        local_map.update({
                            'Key Plans Ratio': 'key_plans_ratio',
                            'Other Layouts': 'other_layouts',
                            'WPR Half Week': 'wpr_half_week',
                            'Manpower Ratio': 'manpower_ratio',
                            'DPR Ratio': 'dpr_ratio',
                            'Manpower Day Ratio': 'manpower_day_ratio'
                        })

                        for excel_col, db_field in local_map.items():
                            if excel_col in row.index:
                                val = clean_num(row[excel_col])
                                # Only save non-zero or if not yet set
                                if val != 0 or db_field not in project_data_map[p_id]:
                                    project_data_map[p_id][db_field] = val

                # --- EXECUTE ---
                process_sheet(sheet_map['sales'], 'sales')
                process_sheet(sheet_map['design'], 'design')
                process_sheet(sheet_map['operation'], 'operation')

                # 3. SAVE TO DB
                Project.objects.all().delete()
                projects_to_create = []
                
                for p_data in project_data_map.values():
                    p = Project(**p_data)
                    projects_to_create.append(p)

                Project.objects.bulk_create(projects_to_create)
                messages.success(request, f"Successfully uploaded {len(projects_to_create)} projects.")
                return redirect('dashboard')

            except Exception as e:
                messages.error(request, f"Upload Failed: {str(e)}")
        else:
            for field, errors in form.errors.items():
                messages.error(request, f"{field}: {errors[0]}")
    else:
        form = UploadFileForm()

    return render(request, 'core/upload.html', {'form': form})

# ==========================================
# 2. DASHBOARD VIEW (Standard)
# ==========================================
def dashboard_view(request):
    # --- 1. SET UP DATES ---
    default_start = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    default_end = datetime.now().strftime('%Y-%m-%d')
    
    view_mode = request.GET.get('view', 'Sales')
    start_date_str = request.GET.get('start', default_start)
    end_date_str = request.GET.get('end', default_end)
    
    # --- 2. DYNAMIC SBU LIST ---
    raw_sbus = Project.objects.values_list('sbu', flat=True).distinct()
    available_sbus = sorted([s for s in raw_sbus if s and str(s).strip() != ''])
    
    if not available_sbus: available_sbus = ['North', 'South', 'West', 'Central']
    
    sbu_filter = request.GET.getlist('sbu')
    if not sbu_filter:
        sbu_filter = available_sbus

    metric_role_filter = request.GET.get('metric_role', 'All Roles')

    # --- 3. FILTER LOGIC ---
    projects = Project.objects.all()

    if sbu_filter:
        projects = projects.filter(sbu__in=sbu_filter)
        
    try:
        start_dt = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_dt = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    except ValueError:
        start_dt = datetime.now().date() - timedelta(days=30)
        end_dt = datetime.now().date()

    roll_start = start_dt - timedelta(days=30*6)
    roll_end = start_dt + timedelta(days=30*8)

    def apply_people_filter(qs, field_name, selected_names):
        if not selected_names: return qs
        q_obj = Q()
        for name in selected_names: q_obj |= Q(**{f"{field_name}__icontains": name})
        return qs.filter(q_obj)

    def get_clean_options(field):
        raw_list = Project.objects.values_list(field, flat=True).distinct()
        clean_list = [x for x in raw_list if x and str(x).strip() != '']
        return sorted(clean_list)

    people_opts = {
        's_head': get_clean_options('sales_head'),
        's_lead': get_clean_options('sales_lead'),
        'd_dh':   get_clean_options('design_dh'),
        'd_dm':   get_clean_options('design_dm'),
        'o_head': get_clean_options('ops_head'),
    }

    selected_filters = {
        's_head': request.GET.getlist('f_s_head'),
        's_lead': request.GET.getlist('f_s_lead'),
        'd_dh': request.GET.getlist('f_d_dh'),
        'd_dm': request.GET.getlist('f_d_dm'),
        'o_head': request.GET.getlist('f_o_head'),
    }

    if view_mode == 'Sales':
        projects = apply_people_filter(projects, 'sales_head', selected_filters['s_head'])
        projects = apply_people_filter(projects, 'sales_lead', selected_filters['s_lead'])
    elif view_mode == 'Design':
        projects = apply_people_filter(projects, 'design_dh', selected_filters['d_dh'])
        projects = apply_people_filter(projects, 'design_dm', selected_filters['d_dm'])
    elif view_mode == 'Operations':
        projects = apply_people_filter(projects, 'ops_head', selected_filters['o_head'])

    # --- 4. METRIC CALCULATION ---
    def calculate_metrics(queryset, metrics, prefix):
        results_prim = []
        results_sec = []
        
        for m in metrics:
            if metric_role_filter != "All Roles" and metric_role_filter not in m['roles']: continue
            
            param_name = f"thresh_{prefix}_{m['field']}"
            user_input = request.GET.get(param_name)
            try: threshold = float(user_input) if user_input else m['def']
            except ValueError: threshold = m['def']

            count = queryset.filter(**{f"{m['field']}__gte": threshold}).count()
            
            item = {'label': m['label'], 'param': param_name, 'threshold': threshold, 'count': count, 'field': m['field']}
            
            if m.get('priority', 'Primary') == 'Primary': results_prim.append(item)
            else: results_sec.append(item)
            
        return results_prim, results_sec

    pre_prim, pre_sec = [], []
    post_prim, post_sec = [], []
    pre_count = 0
    post_count = 0

    if view_mode == 'Sales':
        q_pre = Q(login_date__gte=start_dt) & Q(login_date__lte=end_dt) & Q(stage='Pre Sales')
        pre_projs = projects.filter(q_pre)
        pre_count = pre_projs.count()
        pre_prim, pre_sec = calculate_metrics(pre_projs, METRICS_CONFIG['Sales']['Pre'], 'pre')

        q_post = Q(start_date__gte=roll_start) & Q(start_date__lte=end_dt) & Q(end_date__gte=start_dt) & Q(end_date__lte=roll_end)
        post_projs = projects.filter(q_post)
        post_count = post_projs.count()
        post_prim, post_sec = calculate_metrics(post_projs, METRICS_CONFIG['Sales']['Post'], 'post')

    elif view_mode == 'Design':
        pre_projs = projects.filter(login_date__gte=start_dt, login_date__lte=end_dt)
        pre_count = pre_projs.count()
        pre_prim, pre_sec = calculate_metrics(pre_projs, METRICS_CONFIG['Design']['Pre'], 'pre')
        
        post_projs = projects.filter(start_date__gte=roll_start, start_date__lte=end_dt, end_date__gte=start_dt, end_date__lte=roll_end)
        post_count = post_projs.count()
        post_prim, post_sec = calculate_metrics(post_projs, METRICS_CONFIG['Design']['Post'], 'post')

    elif view_mode == 'Operations':
        post_projs = projects.filter(start_date__gte=roll_start, start_date__lte=end_dt, end_date__gte=start_dt, end_date__lte=roll_end)
        post_count = post_projs.count()
        post_prim, post_sec = calculate_metrics(post_projs, METRICS_CONFIG['Operations'], 'ops')

    has_person_filter = any(key.startswith('f_') and request.GET.get(key) for key in request.GET)

    context = {
        'view_mode': view_mode,
        'start_date': start_date_str,
        'end_date': end_date_str,
        'sbus': available_sbus,
        'selected_sbus': sbu_filter,
        'metric_role_filter': metric_role_filter,
        'people_opts': people_opts,
        'selected_filters': selected_filters,
        'has_person_filter': has_person_filter,
        'pre_prim': pre_prim, 'pre_sec': pre_sec, 'pre_count': pre_count,
        'post_prim': post_prim, 'post_sec': post_sec, 'post_count': post_count,
    }
    return render(request, 'core/dashboard.html', context)

# ==========================================
# 3. REPORT VIEW (Standard)
# ==========================================
def report_view(request):
    default_start = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    default_end = datetime.now().strftime('%Y-%m-%d')
    view_mode = request.GET.get('view', 'Sales')
    start_date_str = request.GET.get('start', default_start)
    end_date_str = request.GET.get('end', default_end)
    sbu_filter = request.GET.getlist('sbu') or ['North', 'South', 'West', 'Central']
    metric_role_filter = request.GET.get('metric_role', 'All Roles')

    projects = Project.objects.all()
    if sbu_filter: projects = projects.filter(sbu__in=sbu_filter)
    
    start_dt = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    end_dt = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    roll_start = start_dt - timedelta(days=30*6)
    roll_end = start_dt + timedelta(days=30*8)

    def apply_people_filter(qs, field_name, selected_names):
        if not selected_names: return qs
        q_obj = Q()
        for name in selected_names: q_obj |= Q(**{f"{field_name}__icontains": name})
        return qs.filter(q_obj)

    if view_mode == 'Sales':
        projects = apply_people_filter(projects, 'sales_head', request.GET.getlist('f_s_head'))
        projects = apply_people_filter(projects, 'sales_lead', request.GET.getlist('f_s_lead'))
    elif view_mode == 'Design':
        projects = apply_people_filter(projects, 'design_dh', request.GET.getlist('f_d_dh'))
        projects = apply_people_filter(projects, 'design_dm', request.GET.getlist('f_d_dm'))
    elif view_mode == 'Operations':
        projects = apply_people_filter(projects, 'ops_head', request.GET.getlist('f_o_head'))

    def get_df(queryset, metrics, prefix):
        data = []
        sorted_metrics = sorted(metrics, key=lambda x: x.get('priority', 'Secondary') == 'Primary', reverse=True)
        for m in sorted_metrics:
            if metric_role_filter != "All Roles" and metric_role_filter not in m['roles']: continue
            param_name = f"thresh_{prefix}_{m['field']}"
            user_input = request.GET.get(param_name)
            try: threshold = float(user_input) if user_input else m['def']
            except ValueError: threshold = m['def']
            count = queryset.filter(**{f"{m['field']}__gte": threshold}).count()
            data.append({"Metric": m['label'], "Threshold Used": threshold, "Projects > Threshold": count})
        return pd.DataFrame(data) if data else pd.DataFrame()

    df_pre = pd.DataFrame()
    df_post = pd.DataFrame()

    if view_mode == 'Sales':
        q_pre = Q(login_date__gte=start_dt) & Q(login_date__lte=end_dt) & Q(stage='Pre Sales')
        df_pre = get_df(projects.filter(q_pre), METRICS_CONFIG['Sales']['Pre'], 'pre')
        q_post = Q(start_date__gte=roll_start) & Q(start_date__lte=end_dt) & Q(end_date__gte=start_dt) & Q(end_date__lte=roll_end)
        df_post = get_df(projects.filter(q_post), METRICS_CONFIG['Sales']['Post'], 'post')
    elif view_mode == 'Design':
        df_pre = get_df(projects.filter(login_date__gte=start_dt, login_date__lte=end_dt), METRICS_CONFIG['Design']['Pre'], 'pre')
        q_post = Q(start_date__gte=roll_start) & Q(start_date__lte=end_dt) & Q(end_date__gte=start_dt) & Q(end_date__lte=roll_end)
        df_post = get_df(projects.filter(q_post), METRICS_CONFIG['Design']['Post'], 'post')
    elif view_mode == 'Operations':
        q_post = Q(start_date__gte=roll_start) & Q(start_date__lte=end_dt) & Q(end_date__gte=start_dt) & Q(end_date__lte=roll_end)
        df_post = get_df(projects.filter(q_post), METRICS_CONFIG['Operations'], 'ops')

    context = {
        'view_mode': view_mode,
        'df_pre': df_pre.to_html(classes='table table-bordered table-striped', index=False) if not df_pre.empty else None,
        'df_post': df_post.to_html(classes='table table-bordered table-striped', index=False) if not df_post.empty else None,
    }
    return render(request, 'core/report.html', context)


# ==========================================
# 4. EXPORT VIEW (Standard)
# ==========================================
def export_view(request):
    default_start = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    default_end = datetime.now().strftime('%Y-%m-%d')
    view_mode = request.GET.get('view', 'Sales')
    start_date_str = request.GET.get('start', default_start)
    end_date_str = request.GET.get('end', default_end)
    sbu_filter = request.GET.getlist('sbu') or ['North', 'South', 'West', 'Central']
    metric_role_filter = request.GET.get('metric_role', 'All Roles')

    projects = Project.objects.all()
    if sbu_filter: projects = projects.filter(sbu__in=sbu_filter)
    
    start_dt = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    end_dt = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    roll_start = start_dt - timedelta(days=30*6)
    roll_end = start_dt + timedelta(days=30*8)

    def apply_people_filter(qs, field_name, selected_names):
        if not selected_names: return qs
        q_obj = Q()
        for name in selected_names: q_obj |= Q(**{f"{field_name}__icontains": name})
        return qs.filter(q_obj)

    if view_mode == 'Sales':
        projects = apply_people_filter(projects, 'sales_head', request.GET.getlist('f_s_head'))
        projects = apply_people_filter(projects, 'sales_lead', request.GET.getlist('f_s_lead'))
    elif view_mode == 'Design':
        projects = apply_people_filter(projects, 'design_dh', request.GET.getlist('f_d_dh'))
        projects = apply_people_filter(projects, 'design_dm', request.GET.getlist('f_d_dm'))
    elif view_mode == 'Operations':
        projects = apply_people_filter(projects, 'ops_head', request.GET.getlist('f_o_head'))

    def generate_summary_df(queryset, metrics, prefix):
        data = []
        # Sort by priority
        sorted_metrics = sorted(metrics, key=lambda x: x.get('priority', 'Secondary') == 'Primary', reverse=True)
        for m in sorted_metrics:
            if metric_role_filter != "All Roles" and metric_role_filter not in m['roles']: continue
            param_name = f"thresh_{prefix}_{m['field']}"
            user_input = request.GET.get(param_name)
            try: threshold = float(user_input) if user_input else m['def']
            except ValueError: threshold = m['def']
            count = queryset.filter(**{f"{m['field']}__gte": threshold}).count()
            data.append({"Metric": m['label'], "Threshold Used": threshold, "Projects > Threshold": count})
        return pd.DataFrame(data) if data else pd.DataFrame()

    df_pre = pd.DataFrame()
    df_post = pd.DataFrame()

    if view_mode == 'Sales':
        q_pre = Q(login_date__gte=start_dt) & Q(login_date__lte=end_dt) & Q(stage='Pre Sales')
        df_pre = generate_summary_df(projects.filter(q_pre), METRICS_CONFIG['Sales']['Pre'], 'pre')
        q_post = Q(start_date__gte=roll_start) & Q(start_date__lte=end_dt) & Q(end_date__gte=start_dt) & Q(end_date__lte=roll_end)
        df_post = generate_summary_df(projects.filter(q_post), METRICS_CONFIG['Sales']['Post'], 'post')
    elif view_mode == 'Design':
        df_pre = generate_summary_df(projects.filter(login_date__gte=start_dt, login_date__lte=end_dt), METRICS_CONFIG['Design']['Pre'], 'pre')
        q_post = Q(start_date__gte=roll_start) & Q(start_date__lte=end_dt) & Q(end_date__gte=start_dt) & Q(end_date__lte=roll_end)
        df_post = generate_summary_df(projects.filter(q_post), METRICS_CONFIG['Design']['Post'], 'post')
    elif view_mode == 'Operations':
        q_post = Q(start_date__gte=roll_start) & Q(start_date__lte=end_dt) & Q(end_date__gte=start_dt) & Q(end_date__lte=roll_end)
        df_post = generate_summary_df(projects.filter(q_post), METRICS_CONFIG['Operations'], 'ops')

    from io import BytesIO

    timestamp = datetime.now().strftime('%H%M')
    filename = f"Summary_{view_mode}_{start_date_str}_{timestamp}.xlsx"
    buffer = BytesIO()

    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        if not df_pre.empty:
            df_pre.to_excel(writer, sheet_name=f'Pre-{view_mode}', index=False)
            ws = writer.sheets[f'Pre-{view_mode}']
            ws.column_dimensions['A'].width = 30
        if not df_post.empty:
            df_post.to_excel(writer, sheet_name=f'Post-{view_mode}', index=False)
            ws = writer.sheets[f'Post-{view_mode}']
            ws.column_dimensions['A'].width = 30
        if df_pre.empty and df_post.empty:
            pd.DataFrame({'Info': ['No data found']}).to_excel(writer, sheet_name='No Data', index=False)

    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    return response