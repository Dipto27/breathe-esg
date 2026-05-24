from rest_framework import serializers
from .models import Client, DataSource, IngestionJob, EmissionRecord, AuditEntry
from django.contrib.auth.models import User


class ClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = ['id', 'name', 'slug', 'created_at']


class DataSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataSource
        fields = ['id', 'client', 'source_type', 'label', 'created_at']
        read_only_fields = ['client']


class IngestionJobSerializer(serializers.ModelSerializer):
    data_source_label = serializers.CharField(source='data_source.label', read_only=True)
    source_type = serializers.CharField(source='data_source.source_type', read_only=True)

    class Meta:
        model = IngestionJob
        fields = [
            'id', 'data_source', 'data_source_label', 'source_type',
            'status', 'row_count', 'error_count', 'errors',
            'started_at', 'completed_at', 'created_at',
        ]


class EmissionRecordSerializer(serializers.ModelSerializer):
    reviewed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = EmissionRecord
        fields = [
            'id', 'source_type', 'source_row_ref', 'scope', 'category',
            'activity_description', 'quantity', 'unit',
            'quantity_normalized', 'unit_normalized',
            'emission_factor', 'emission_factor_source', 'co2e_kg',
            'cost', 'currency',
            'activity_date', 'billing_period_start', 'billing_period_end',
            'facility_code', 'facility_name', 'cost_center',
            'origin', 'destination', 'traveler_id',
            'status', 'flag_reason', 'reviewed_by_name', 'reviewed_at',
            'ingestion_job', 'created_at', 'updated_at',
        ]

    def get_reviewed_by_name(self, obj):
        if obj.reviewed_by:
            return obj.reviewed_by.get_full_name() or obj.reviewed_by.username
        return None


class AuditEntrySerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = AuditEntry
        fields = ['id', 'action', 'actor_name', 'timestamp', 'notes', 'diff']

    def get_actor_name(self, obj):
        if obj.actor:
            return obj.actor.get_full_name() or obj.actor.username
        return 'System'
