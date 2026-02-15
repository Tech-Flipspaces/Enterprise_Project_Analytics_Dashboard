# core/urls.py

from django.urls import path                # type: ignore
from . import views

urlpatterns = [
    # --- Dashboard & Ingestion ---
    path('', views.dashboard_view, name='dashboard'),
    path('upload/', views.upload_view, name='upload'),

    # --- Live Reporting ---
    path('report/', views.report_view, name='report'),
    path('report-detailed/', views.report_detailed_view, name='report_detailed'),

    # --- Excel Exports ---
    path('export/', views.export_view, name='export_data'),
    path('export-detailed/', views.export_detailed_view, name='export_detailed'),

    # --- Project Analytics ---
    path('project/<int:pk>/', views.project_detail, name='project_detail'),
    path('scorecard/<str:project_code>/', views.project_scorecard_view, name='project_scorecard'),

    # --- Performance Leaderboards ---
    path('leaderboard/', views.leaderboard_view, name='leaderboard'),
    path('leaderboard/summary/', views.leaderboard_summary_view, name='leaderboard_summary'),
]