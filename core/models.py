from django.db import models            # type:ignore

class Project(models.Model):
    # --- ID & Metadata ---
    project_code = models.CharField(max_length=50, unique=True)
    project_name = models.CharField(max_length=255, null=True, blank=True)
    sbu = models.CharField(max_length=50, null=True, blank=True)
    stage = models.CharField(max_length=50, null=True, blank=True)
    
    # --- Dates ---
    login_date = models.DateField(null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    
    # --- Team ---
    sales_head = models.CharField(max_length=100, null=True, blank=True)
    sales_lead = models.CharField(max_length=100, null=True, blank=True)
    design_dh = models.CharField(max_length=100, null=True, blank=True)
    design_dm = models.CharField(max_length=100, null=True, blank=True)
    design_id = models.CharField(max_length=100, null=True, blank=True)
    design_3d = models.CharField(max_length=100, null=True, blank=True)
    ops_head = models.CharField(max_length=100, null=True, blank=True)
    ops_pm = models.CharField(max_length=100, null=True, blank=True)
    ops_om = models.CharField(max_length=100, null=True, blank=True)
    ops_ss = models.CharField(max_length=100, null=True, blank=True)
    ops_mep = models.CharField(max_length=100, null=True, blank=True)
    ops_csc = models.CharField(max_length=100, null=True, blank=True)

    # =========================================================
    # METRICS (Must match constants.py EXCEL_COL_MAP keys exactly)
    # =========================================================

    # --- Sales Metrics ---
    req_uploaded = models.FloatField(default=0.0)
    site_visit_report = models.FloatField(default=0.0)
    client_access = models.FloatField(default=0.0)
    boq_uploaded = models.FloatField(default=0.0)
    contract_uploaded = models.FloatField(default=0.0)
    boq = models.FloatField(default=0.0)         
    contract = models.FloatField(default=0.0)    

    # --- Design Metrics ---
    furniture_layouts = models.FloatField(default=0.0)
    approved_layouts = models.FloatField(default=0.0)
    mapped_spaces = models.FloatField(default=0.0)
    no_plans_for_key_spaces = models.FloatField(default=0.0)
    renders = models.FloatField(default=0.0)
    approved_renders = models.FloatField(default=0.0)
    td_elevations = models.FloatField(default=0.0)
    cad_files = models.FloatField(default=0.0)
    slides_download = models.FloatField(default=0.0)
    material_deck = models.FloatField(default=0.0)
    gfc_download = models.FloatField(default=0.0)
    client_visit_des = models.FloatField(default=0.0)
    
    # Calculated Design Metrics
    key_plans_ratio = models.FloatField(default=0.0)
    other_layouts = models.FloatField(default=0.0)

    # --- Ops Metrics ---
    site_images = models.FloatField(default=0.0)
    invoices = models.FloatField(default=0.0)
    mep_drawings = models.FloatField(default=0.0)
    handover_docs = models.FloatField(default=0.0)
    wpr_download = models.FloatField(default=0.0)
    wpr_shared = models.FloatField(default=0.0)
    weekly_tasks = models.FloatField(default=0.0)
    daily_tasks = models.FloatField(default=0.0)
    grn_created = models.FloatField(default=0.0)
    grn_approved = models.FloatField(default=0.0)
    
    # Calculated Ops Metrics
    wpr_half_week = models.FloatField(default=0.0)
    manpower_ratio = models.FloatField(default=0.0)
    dpr_ratio = models.FloatField(default=0.0)
    manpower_day_ratio = models.FloatField(default=0.0)

    def __str__(self):
        return self.project_code