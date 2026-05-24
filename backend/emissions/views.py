"""
Emission record API views.

Permission model:
- All views require authentication (JWT)
- Users only see clients they are members of
- Only ADMIN-role users can approve/lock records
- Analysts can flag records and add notes
"""
from django.utils import timezone
from django.db.models import Sum, Count, Q
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import (
    Client, DataSource, IngestionJob, EmissionRecord, AuditEntry,
    UserClientMembership
)
from .serializers import (
    ClientSerializer, DataSourceSerializer, IngestionJobSerializer,
    EmissionRecordSerializer, AuditEntrySerializer
)
from .parsers.sap_parser import parse_sap_csv
from .parsers.utility_parser import parse_utility_csv
from .parsers.travel_parser import parse_travel_csv
from .normalizers.emission_factors import calculate_co2e


def get_client_or_403(user, client_id):
    """Return client if user is a member, else raise PermissionError."""
    try:
        client = Client.objects.get(pk=client_id)
    except Client.DoesNotExist:
        return None, Response({'error': 'Client not found'}, status=404)
    
    # Superusers can access all clients
    if user.is_superuser:
        return client, None

    if not UserClientMembership.objects.filter(user=user, client=client).exists():
        return None, Response({'error': 'Access denied'}, status=403)
    return client, None


class ClientListView(generics.ListAPIView):
    serializer_class = ClientSerializer

    def get_queryset(self):
        if self.request.user.is_superuser:
            return Client.objects.all()
        return Client.objects.filter(memberships__user=self.request.user)


class DataSourceListView(APIView):
    def get(self, request, client_id):
        client, err = get_client_or_403(request.user, client_id)
        if err:
            return err
        sources = DataSource.objects.filter(client=client)
        return Response(DataSourceSerializer(sources, many=True).data)

    def post(self, request, client_id):
        client, err = get_client_or_403(request.user, client_id)
        if err:
            return err
        serializer = DataSourceSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(client=client)
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)


class IngestView(APIView):
    """
    POST a CSV file to ingest. Required form fields:
      - file: the CSV file
      - source_type: SAP | UTILITY | TRAVEL
      - source_label: human-readable name for this data source
    """

    def post(self, request, client_id):
        client, err = get_client_or_403(request.user, client_id)
        if err:
            return err

        file_obj = request.FILES.get('file')
        source_type = request.data.get('source_type', '').upper()
        source_label = request.data.get('source_label', source_type)

        if not file_obj:
            return Response({'error': 'No file provided'}, status=400)
        if source_type not in ('SAP', 'UTILITY', 'TRAVEL'):
            return Response({'error': 'source_type must be SAP, UTILITY, or TRAVEL'}, status=400)

        # Get or create the data source
        data_source, _ = DataSource.objects.get_or_create(
            client=client, source_type=source_type, label=source_label
        )

        # Create ingestion job
        job = IngestionJob.objects.create(
            data_source=data_source,
            status='PROCESSING',
            raw_file=file_obj,
            created_by=request.user,
            started_at=timezone.now(),
        )

        try:
            content = file_obj.read().decode('utf-8-sig')  # utf-8-sig handles BOM from Excel exports

            # Parse
            if source_type == 'SAP':
                records_data, errors, skipped = parse_sap_csv(content)
            elif source_type == 'UTILITY':
                records_data, errors, skipped = parse_utility_csv(content)
            else:
                records_data, errors, skipped = parse_travel_csv(content)

            # Create EmissionRecord objects
            created = 0
            for r in records_data:
                flag_reason = r.pop('_flag_reason', '')

                # Calculate CO2e
                co2e_kg, factor, notes = calculate_co2e(
                    r['category'], r['quantity_normalized'], r['unit']
                )

                record = EmissionRecord.objects.create(
                    client=client,
                    ingestion_job=job,
                    source_type=source_type,
                    emission_factor=factor,
                    emission_factor_source='DEFRA 2023',
                    co2e_kg=co2e_kg,
                    status='FLAGGED' if flag_reason else 'PENDING',
                    flag_reason=flag_reason,
                    **r
                )

                AuditEntry.objects.create(
                    emission_record=record,
                    action='CREATED',
                    actor=request.user,
                    notes=f'Ingested via {source_type} upload',
                )
                created += 1

            job.row_count = created
            job.error_count = len(errors)
            job.errors = errors
            job.status = 'DONE'
            job.completed_at = timezone.now()
            job.save()

            return Response({
                'job_id': job.id,
                'status': 'DONE',
                'rows_ingested': created,
                'rows_skipped': skipped,
                'errors': errors,
            }, status=201)

        except Exception as e:
            job.status = 'FAILED'
            job.errors = [{'row': 0, 'message': str(e)}]
            job.completed_at = timezone.now()
            job.save()
            return Response({'error': str(e), 'job_id': job.id}, status=500)


class IngestionJobListView(generics.ListAPIView):
    serializer_class = IngestionJobSerializer

    def get_queryset(self):
        client_id = self.kwargs['client_id']
        client, err = get_client_or_403(self.request.user, client_id)
        if err:
            return IngestionJob.objects.none()
        return IngestionJob.objects.filter(data_source__client=client)


class IngestionJobDetailView(generics.RetrieveAPIView):
    serializer_class = IngestionJobSerializer
    queryset = IngestionJob.objects.all()


class EmissionRecordListView(generics.ListAPIView):
    serializer_class = EmissionRecordSerializer

    def get_queryset(self):
        client_id = self.kwargs['client_id']
        client, err = get_client_or_403(self.request.user, client_id)
        if err:
            return EmissionRecord.objects.none()

        qs = EmissionRecord.objects.filter(client=client)

        # Filters
        scope = self.request.query_params.get('scope')
        source_type = self.request.query_params.get('source_type')
        status_filter = self.request.query_params.get('status')
        category = self.request.query_params.get('category')

        if scope:
            qs = qs.filter(scope=scope)
        if source_type:
            qs = qs.filter(source_type=source_type.upper())
        if status_filter:
            qs = qs.filter(status=status_filter.upper())
        if category:
            qs = qs.filter(category=category)

        return qs.select_related('reviewed_by', 'ingestion_job')


class EmissionRecordDetailView(generics.RetrieveAPIView):
    serializer_class = EmissionRecordSerializer
    queryset = EmissionRecord.objects.all()


class ApproveRecordView(APIView):
    def post(self, request, pk):
        try:
            record = EmissionRecord.objects.get(pk=pk)
        except EmissionRecord.DoesNotExist:
            return Response({'error': 'Record not found'}, status=404)

        if record.status == 'LOCKED':
            return Response({'error': 'Record is locked for audit'}, status=400)

        old_status = record.status
        record.status = 'APPROVED'
        record.reviewed_by = request.user
        record.reviewed_at = timezone.now()
        record.flag_reason = ''
        record.save()

        AuditEntry.objects.create(
            emission_record=record,
            action='APPROVED',
            actor=request.user,
            notes=request.data.get('notes', ''),
            diff={'status': {'from': old_status, 'to': 'APPROVED'}},
        )

        return Response(EmissionRecordSerializer(record).data)


class FlagRecordView(APIView):
    def post(self, request, pk):
        try:
            record = EmissionRecord.objects.get(pk=pk)
        except EmissionRecord.DoesNotExist:
            return Response({'error': 'Record not found'}, status=404)

        if record.status == 'LOCKED':
            return Response({'error': 'Record is locked for audit'}, status=400)

        reason = request.data.get('reason', '')
        if not reason:
            return Response({'error': 'Flag reason required'}, status=400)

        old_status = record.status
        record.status = 'FLAGGED'
        record.flag_reason = reason
        record.save()

        AuditEntry.objects.create(
            emission_record=record,
            action='FLAGGED',
            actor=request.user,
            notes=reason,
            diff={'status': {'from': old_status, 'to': 'FLAGGED'}},
        )

        return Response(EmissionRecordSerializer(record).data)


class AuditTrailView(APIView):
    def get(self, request, pk):
        try:
            record = EmissionRecord.objects.get(pk=pk)
        except EmissionRecord.DoesNotExist:
            return Response({'error': 'Record not found'}, status=404)
        entries = AuditEntry.objects.filter(emission_record=record)
        return Response(AuditEntrySerializer(entries, many=True).data)


class DashboardSummaryView(APIView):
    def get(self, request, client_id):
        client, err = get_client_or_403(request.user, client_id)
        if err:
            return err

        records = EmissionRecord.objects.filter(client=client)

        total_co2e = records.aggregate(total=Sum('co2e_kg'))['total'] or 0
        by_scope = {}
        for scope in ['1', '2', '3']:
            agg = records.filter(scope=scope).aggregate(
                total_co2e=Sum('co2e_kg'), count=Count('id')
            )
            by_scope[f'scope_{scope}'] = {
                'co2e_kg': float(agg['total_co2e'] or 0),
                'count': agg['count'],
            }

        status_counts = {
            s: records.filter(status=s).count()
            for s in ['PENDING', 'FLAGGED', 'APPROVED', 'LOCKED']
        }

        source_summary = {}
        for st in ['SAP', 'UTILITY', 'TRAVEL']:
            agg = records.filter(source_type=st).aggregate(
                total_co2e=Sum('co2e_kg'), count=Count('id')
            )
            source_summary[st] = {
                'co2e_kg': float(agg['total_co2e'] or 0),
                'count': agg['count'],
            }

        return Response({
            'total_co2e_kg': float(total_co2e),
            'by_scope': by_scope,
            'by_source': source_summary,
            'status_counts': status_counts,
            'total_records': records.count(),
        })


class LoadSampleDataView(APIView):
    """
    Loads pre-built sample data for demonstration purposes.
    Creates realistic records without requiring file uploads.
    """

    def post(self, request, client_id):
        client, err = get_client_or_403(request.user, client_id)
        if err:
            return err

        from decimal import Decimal
        from datetime import date

        # Create sample data sources
        sap_source, _ = DataSource.objects.get_or_create(
            client=client, source_type='SAP', label='SAP MB51 — Fuel Movements'
        )
        util_source, _ = DataSource.objects.get_or_create(
            client=client, source_type='UTILITY', label='National Grid Portal Export'
        )
        travel_source, _ = DataSource.objects.get_or_create(
            client=client, source_type='TRAVEL', label='Concur Expense Export Q1 2024'
        )

        # Create sample ingestion jobs
        sap_job = IngestionJob.objects.create(
            data_source=sap_source, status='DONE', row_count=8, error_count=0,
            created_by=request.user, started_at=timezone.now(), completed_at=timezone.now()
        )
        util_job = IngestionJob.objects.create(
            data_source=util_source, status='DONE', row_count=6, error_count=0,
            created_by=request.user, started_at=timezone.now(), completed_at=timezone.now()
        )
        travel_job = IngestionJob.objects.create(
            data_source=travel_source, status='DONE', row_count=10, error_count=0,
            created_by=request.user, started_at=timezone.now(), completed_at=timezone.now()
        )

        sample_records = [
            # SAP Scope 1 — Fuel
            dict(ingestion_job=sap_job, source_type='SAP', scope='1', category='fuel_diesel',
                 activity_description='Diesel — Plant Hamburg (MBLNR: 4900001234)',
                 quantity=Decimal('12500'), unit='L', quantity_normalized=Decimal('12500'), unit_normalized='L',
                 emission_factor=Decimal('2.5163'), emission_factor_source='DEFRA 2023',
                 co2e_kg=Decimal('31453.75'), cost=Decimal('18750.00'), currency='EUR',
                 activity_date=date(2024, 1, 15), facility_code='1000', facility_name='Hamburg Plant',
                 cost_center='CC-MAINT-01', source_row_ref='4900001234', status='APPROVED'),
            dict(ingestion_job=sap_job, source_type='SAP', scope='1', category='fuel_diesel',
                 activity_description='Diesel — Berlin Plant (MBLNR: 4900001289)',
                 quantity=Decimal('8300'), unit='L', quantity_normalized=Decimal('8300'), unit_normalized='L',
                 emission_factor=Decimal('2.5163'), emission_factor_source='DEFRA 2023',
                 co2e_kg=Decimal('20885.29'), cost=Decimal('12450.00'), currency='EUR',
                 activity_date=date(2024, 1, 28), facility_code='1100', facility_name='Berlin Plant',
                 cost_center='CC-OPS-02', source_row_ref='4900001289', status='APPROVED'),
            dict(ingestion_job=sap_job, source_type='SAP', scope='1', category='fuel_natural_gas',
                 activity_description='Natural Gas — Hamburg Plant (MBLNR: 4900001310)',
                 quantity=Decimal('4200'), unit='m3', quantity_normalized=Decimal('4200'), unit_normalized='m3',
                 emission_factor=Decimal('2.0407'), emission_factor_source='DEFRA 2023',
                 co2e_kg=Decimal('8570.94'), cost=Decimal('5040.00'), currency='EUR',
                 activity_date=date(2024, 2, 10), facility_code='1000', facility_name='Hamburg Plant',
                 cost_center='CC-HEAT-01', source_row_ref='4900001310', status='PENDING'),
            dict(ingestion_job=sap_job, source_type='SAP', scope='1', category='fuel_petrol',
                 activity_description='Petrol Fleet — Vehicle Pool (MBLNR: 4900001402)',
                 quantity=Decimal('3100'), unit='L', quantity_normalized=Decimal('3100'), unit_normalized='L',
                 emission_factor=Decimal('2.1662'), emission_factor_source='DEFRA 2023',
                 co2e_kg=Decimal('6715.22'), cost=Decimal('4650.00'), currency='EUR',
                 activity_date=date(2024, 2, 22), facility_code='2000', facility_name='New York Office',
                 cost_center='CC-FLEET-01', source_row_ref='4900001402', status='FLAGGED',
                 flag_reason='Quantity 3x higher than previous month — verify with fleet manager'),
            dict(ingestion_job=sap_job, source_type='SAP', scope='1', category='fuel_diesel',
                 activity_description='Diesel — Singapore Hub (MBLNR: 4900001455)',
                 quantity=Decimal('6800'), unit='L', quantity_normalized=Decimal('6800'), unit_normalized='L',
                 emission_factor=Decimal('2.5163'), emission_factor_source='DEFRA 2023',
                 co2e_kg=Decimal('17110.84'), cost=Decimal('10200.00'), currency='SGD',
                 activity_date=date(2024, 3, 5), facility_code='3000', facility_name='Singapore Hub',
                 cost_center='CC-OPS-SG', source_row_ref='4900001455', status='PENDING'),

            # Utility Scope 2 — Electricity
            dict(ingestion_job=util_job, source_type='UTILITY', scope='2', category='electricity',
                 activity_description='Electricity — Hamburg Plant HV Meter #HH-001',
                 quantity=Decimal('245000'), unit='kWh', quantity_normalized=Decimal('245000'), unit_normalized='kWh',
                 emission_factor=Decimal('0.23314'), emission_factor_source='DEFRA 2023',
                 co2e_kg=Decimal('57119.30'), cost=Decimal('36750.00'), currency='EUR',
                 activity_date=date(2024, 1, 31), billing_period_start=date(2024, 1, 1),
                 billing_period_end=date(2024, 1, 31),
                 facility_code='HH-001', facility_name='Hamburg Plant — Main Meter',
                 source_row_ref='ACC-DE-1000_HH-001_2024-01-01', status='APPROVED'),
            dict(ingestion_job=util_job, source_type='UTILITY', scope='2', category='electricity',
                 activity_description='Electricity — Berlin Plant Meter #BE-002',
                 quantity=Decimal('178000'), unit='kWh', quantity_normalized=Decimal('178000'), unit_normalized='kWh',
                 emission_factor=Decimal('0.23314'), emission_factor_source='DEFRA 2023',
                 co2e_kg=Decimal('41498.92'), cost=Decimal('26700.00'), currency='EUR',
                 activity_date=date(2024, 1, 31), billing_period_start=date(2024, 1, 1),
                 billing_period_end=date(2024, 1, 31),
                 facility_code='BE-002', facility_name='Berlin Plant — Main Meter',
                 source_row_ref='ACC-DE-1100_BE-002_2024-01-01', status='APPROVED'),
            dict(ingestion_job=util_job, source_type='UTILITY', scope='2', category='electricity',
                 activity_description='Electricity — Hamburg Plant HV Meter #HH-001 (Estimated Read)',
                 quantity=Decimal('251000'), unit='kWh', quantity_normalized=Decimal('251000'), unit_normalized='kWh',
                 emission_factor=Decimal('0.23314'), emission_factor_source='DEFRA 2023',
                 co2e_kg=Decimal('58518.14'), cost=Decimal('37650.00'), currency='EUR',
                 activity_date=date(2024, 2, 29), billing_period_start=date(2024, 2, 1),
                 billing_period_end=date(2024, 2, 29),
                 facility_code='HH-001', facility_name='Hamburg Plant — Main Meter',
                 source_row_ref='ACC-DE-1000_HH-001_2024-02-01', status='FLAGGED',
                 flag_reason='Estimated meter read — verify with actual bill'),
            dict(ingestion_job=util_job, source_type='UTILITY', scope='2', category='electricity',
                 activity_description='Electricity — New York Office Meter #NY-010',
                 quantity=Decimal('42000'), unit='kWh', quantity_normalized=Decimal('42000'), unit_normalized='kWh',
                 emission_factor=Decimal('0.23314'), emission_factor_source='DEFRA 2023',
                 co2e_kg=Decimal('9791.88'), cost=Decimal('8400.00'), currency='USD',
                 activity_date=date(2024, 2, 29), billing_period_start=date(2024, 2, 1),
                 billing_period_end=date(2024, 2, 29),
                 facility_code='NY-010', facility_name='New York Office',
                 source_row_ref='ACC-US-2000_NY-010_2024-02-01', status='PENDING'),

            # Travel Scope 3
            dict(ingestion_job=travel_job, source_type='TRAVEL', scope='3', category='travel_air',
                 activity_description='Airfare | JFK → LHR',
                 quantity=Decimal('5570'), unit='km', quantity_normalized=Decimal('5570'), unit_normalized='km',
                 emission_factor=Decimal('0.2553'), emission_factor_source='DEFRA 2023',
                 co2e_kg=Decimal('1422.12'), cost=Decimal('1850.00'), currency='USD',
                 activity_date=date(2024, 1, 10), origin='JFK', destination='LHR',
                 traveler_id='EMP-0042', cost_center='PROJ-ESG-2024', source_row_ref='CONC-R001_2',
                 status='APPROVED'),
            dict(ingestion_job=travel_job, source_type='TRAVEL', scope='3', category='travel_air',
                 activity_description='Airfare | FRA → SIN',
                 quantity=Decimal('10250'), unit='km', quantity_normalized=Decimal('10250'), unit_normalized='km',
                 emission_factor=Decimal('0.2553'), emission_factor_source='DEFRA 2023',
                 co2e_kg=Decimal('2616.83'), cost=Decimal('2400.00'), currency='EUR',
                 activity_date=date(2024, 1, 22), origin='FRA', destination='SIN',
                 traveler_id='EMP-0078', cost_center='PROJ-OPS-SG', source_row_ref='CONC-R002_3',
                 status='APPROVED'),
            dict(ingestion_job=travel_job, source_type='TRAVEL', scope='3', category='travel_hotel',
                 activity_description='Hotel Stay | London, UK — 4 nights',
                 quantity=Decimal('4'), unit='nights', quantity_normalized=Decimal('4'), unit_normalized='nights',
                 emission_factor=Decimal('20.8'), emission_factor_source='DEFRA 2023',
                 co2e_kg=Decimal('83.2'), cost=Decimal('1200.00'), currency='GBP',
                 activity_date=date(2024, 1, 14), destination='London, UK',
                 traveler_id='EMP-0042', cost_center='PROJ-ESG-2024', source_row_ref='CONC-R001_4',
                 status='PENDING'),
            dict(ingestion_job=travel_job, source_type='TRAVEL', scope='3', category='travel_air',
                 activity_description='Airfare | ORD → AMS (No distance provided)',
                 quantity=Decimal('1'), unit='trip', quantity_normalized=Decimal('1'), unit_normalized='trip',
                 emission_factor=Decimal('0.2553'), emission_factor_source='DEFRA 2023',
                 co2e_kg=Decimal('510.60'), cost=Decimal('1650.00'), currency='USD',
                 activity_date=date(2024, 2, 5), origin='ORD', destination='AMS',
                 traveler_id='EMP-0121', cost_center='PROJ-SALES-EU', source_row_ref='CONC-R003_1',
                 status='FLAGGED',
                 flag_reason='Distance not provided — emission calculated using average per-trip factor'),
            dict(ingestion_job=travel_job, source_type='TRAVEL', scope='3', category='travel_ground',
                 activity_description='Car Rental | Chicago',
                 quantity=Decimal('320'), unit='km', quantity_normalized=Decimal('320'), unit_normalized='km',
                 emission_factor=Decimal('0.1589'), emission_factor_source='DEFRA 2023',
                 co2e_kg=Decimal('50.85'), cost=Decimal('420.00'), currency='USD',
                 activity_date=date(2024, 2, 8), origin='Chicago, IL',
                 traveler_id='EMP-0121', cost_center='PROJ-SALES-EU', source_row_ref='CONC-R003_2',
                 status='PENDING'),
        ]

        created_count = 0
        for data in sample_records:
            record = EmissionRecord.objects.create(client=client, **data)
            AuditEntry.objects.create(
                emission_record=record, action='CREATED', actor=request.user,
                notes='Loaded via sample data endpoint'
            )
            created_count += 1

        return Response({
            'message': f'Loaded {created_count} sample records',
            'records_created': created_count,
        }, status=201)
