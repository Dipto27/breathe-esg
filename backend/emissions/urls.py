from django.urls import path
from . import views

urlpatterns = [
    # Clients
    path('clients/', views.ClientListView.as_view(), name='client-list'),

    # Data sources
    path('clients/<int:client_id>/sources/', views.DataSourceListView.as_view(), name='source-list'),

    # Ingestion jobs
    path('clients/<int:client_id>/ingest/', views.IngestView.as_view(), name='ingest'),
    path('clients/<int:client_id>/jobs/', views.IngestionJobListView.as_view(), name='job-list'),
    path('jobs/<int:pk>/', views.IngestionJobDetailView.as_view(), name='job-detail'),

    # Emission records
    path('clients/<int:client_id>/records/', views.EmissionRecordListView.as_view(), name='record-list'),
    path('records/<int:pk>/', views.EmissionRecordDetailView.as_view(), name='record-detail'),
    path('records/<int:pk>/approve/', views.ApproveRecordView.as_view(), name='record-approve'),
    path('records/<int:pk>/flag/', views.FlagRecordView.as_view(), name='record-flag'),
    path('records/<int:pk>/audit/', views.AuditTrailView.as_view(), name='record-audit'),

    # Dashboard summary
    path('clients/<int:client_id>/summary/', views.DashboardSummaryView.as_view(), name='dashboard-summary'),

    # Sample data generation for demo
    path('clients/<int:client_id>/load-samples/', views.LoadSampleDataView.as_view(), name='load-samples'),
]
