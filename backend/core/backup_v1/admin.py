from django.contrib import admin            # type: ignore
from .models import Project, Department, UserGroup, Metric, SuccessMetric

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('project_code', 'project_name', 'sbu', 'stage')
    search_fields = ('project_code', 'project_name')

admin.site.register(Department)  # DELETE THIS AT LAST, COZ DEPT. ARE FIXED NUMBERS AND NOT LIKELY TO ADD NEW ONES.
admin.site.register(UserGroup)
admin.site.register(SuccessMetric)

@admin.register(Metric)
class MetricAdmin(admin.ModelAdmin):
    list_display = ('label', 'department', 'stage', 'get_groups', 'credit_weight', 'is_manual_credit', 'success_metric')
    list_filter = ('department', 'stage', 'success_metric')

    list_editable = ('is_manual_credit',) # Allows quick toggling in the list view
    filter_horizontal = ('visible_to_groups',)
    
    # Fields to show in the edit form
    fieldsets = (
        ('Basic Info', {
            'fields': ('label', 'field_name', 'department', 'stage', 'visible_to_groups')
        }),
        ('Logic & Thresholds', {
            'fields': ('default_threshold', 'success_metric'),
        }),
        ('Credit System', {
            'fields': ('is_manual_credit', 'credit_weight'),
            'description': 'If Manual is checked, enter the weight below. Otherwise, weight is auto-calculated.'
        }),
    )

    @admin.display(description='User Groups')
    def get_groups(self, obj):
        return ", ".join([g.name for g in obj.visible_to_groups.all()])
    
    # Phase 2: Signal logic will go here later to auto-calc credits