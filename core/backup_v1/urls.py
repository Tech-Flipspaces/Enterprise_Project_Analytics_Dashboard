from django.urls import path
from . import views

urlpatterns = [
    # 1. Dashboard (The Homepage)
    path('', views.dashboard_view, name='dashboard'),

    # 2. Upload Page (To process new Excel files)
    path('upload/', views.upload_view, name='upload'),

    # 3. Live Report (The HTML table in a new tab)
    path('report/', views.report_view, name='report'),

    # 4. Summary Export (The Excel download logic)
    path('export/', views.export_view, name='export'),
]