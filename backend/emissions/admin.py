from django.contrib import admin
from .models import Client, UserClientMembership, DataSource, IngestionJob, EmissionRecord, AuditEntry

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'created_at']
    prepopulated_fields = {'slug': ('name',)}

@admin.register(UserClientMembership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ['user', 'client', 'role']

@admin.register(DataSource)
class DataSourceAdmin(admin.ModelAdmin):
    list_display = ['client', 'source_type', 'label']

@admin.register(IngestionJob)
class IngestionJobAdmin(admin.ModelAdmin):
    list_display = ['id', 'data_source', 'status', 'row_count', 'error_count', 'created_at']
    list_filter = ['status']

@admin.register(EmissionRecord)
class EmissionRecordAdmin(admin.ModelAdmin):
    list_display = ['id', 'client', 'source_type', 'scope', 'category', 'quantity', 'unit', 'co2e_kg', 'status']
    list_filter = ['scope', 'source_type', 'status', 'client']
    search_fields = ['activity_description', 'source_row_ref']

@admin.register(AuditEntry)
class AuditEntryAdmin(admin.ModelAdmin):
    list_display = ['emission_record', 'action', 'actor', 'timestamp']
    list_filter = ['action']
