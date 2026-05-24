"""
Core data models for Breathe ESG emissions tracking.

Design decisions:
- Multi-tenancy via Client FK on every record (row-level isolation)
- EmissionRecord is the canonical normalized form regardless of source
- AuditEntry provides immutable append-only audit trail
- IngestionJob tracks raw file state for traceability
- status field enables analyst review workflow with soft-lock before audit
"""
from django.db import models
from django.contrib.auth.models import User


class Client(models.Model):
    """
    Represents an enterprise client company.
    All data is scoped to a client — analysts only see their own client's data.
    """
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']


class UserClientMembership(models.Model):
    """Links a Django user to one or more clients with a role."""
    ROLE_CHOICES = [('ANALYST', 'Analyst'), ('ADMIN', 'Admin')]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='memberships')
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='memberships')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='ANALYST')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'client')

    def __str__(self):
        return f"{self.user.username} → {self.client.name} ({self.role})"


class DataSource(models.Model):
    """
    Configuration for a data source connected to a client.
    Tracks what type of data comes from where.
    """
    SOURCE_TYPE_CHOICES = [
        ('SAP', 'SAP Fuel & Procurement'),
        ('UTILITY', 'Utility / Electricity'),
        ('TRAVEL', 'Corporate Travel'),
    ]
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='data_sources')
    source_type = models.CharField(max_length=20, choices=SOURCE_TYPE_CHOICES)
    label = models.CharField(max_length=255, help_text="Human-readable label, e.g. 'HQ Electricity Meter'")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.client.slug} / {self.source_type} / {self.label}"


class IngestionJob(models.Model):
    """
    Represents one upload/ingest event — a batch of rows from a single file or API pull.
    Preserves the raw file so we can re-parse if normalization logic changes.
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('DONE', 'Done'),
        ('FAILED', 'Failed'),
    ]
    data_source = models.ForeignKey(DataSource, on_delete=models.CASCADE, related_name='jobs')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    raw_file = models.FileField(upload_to='ingestion_files/', null=True, blank=True)
    row_count = models.IntegerField(default=0)
    error_count = models.IntegerField(default=0)
    errors = models.JSONField(default=list)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Job {self.pk} — {self.data_source} [{self.status}]"

    class Meta:
        ordering = ['-created_at']


class EmissionRecord(models.Model):
    """
    The canonical normalized record — one logical emission activity row.
    
    Scope assignment:
      Scope 1 — Direct combustion (SAP fuel data)
      Scope 2 — Purchased electricity (Utility data)
      Scope 3 — Indirect value chain (Corporate travel)
    
    All monetary and quantity values preserve originals alongside normalized forms
    so analysts can verify normalization without losing source context.
    """
    SCOPE_CHOICES = [('1', 'Scope 1'), ('2', 'Scope 2'), ('3', 'Scope 3')]
    CATEGORY_CHOICES = [
        ('fuel_diesel', 'Diesel Combustion'),
        ('fuel_petrol', 'Petrol/Gasoline Combustion'),
        ('fuel_natural_gas', 'Natural Gas Combustion'),
        ('fuel_lpg', 'LPG Combustion'),
        ('fuel_other', 'Other Fuel Combustion'),
        ('electricity', 'Purchased Electricity'),
        ('travel_air', 'Air Travel'),
        ('travel_hotel', 'Hotel Stay'),
        ('travel_ground', 'Ground Transport'),
        ('travel_rail', 'Rail Travel'),
    ]
    STATUS_CHOICES = [
        ('PENDING', 'Pending Review'),
        ('FLAGGED', 'Flagged for Review'),
        ('APPROVED', 'Approved'),
        ('LOCKED', 'Locked for Audit'),
    ]

    # Provenance
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='records')
    ingestion_job = models.ForeignKey(IngestionJob, on_delete=models.CASCADE, related_name='records')
    source_type = models.CharField(max_length=20, choices=[
        ('SAP', 'SAP'), ('UTILITY', 'Utility'), ('TRAVEL', 'Travel')
    ])
    source_row_ref = models.CharField(max_length=255, blank=True, help_text="Original row ID/document number from source")

    # Emission classification
    scope = models.CharField(max_length=1, choices=SCOPE_CHOICES)
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES)

    # Activity description
    activity_description = models.TextField(blank=True)

    # Quantities — original and normalized
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    unit = models.CharField(max_length=20, help_text="Original unit from source (L, kWh, km, nights, etc.)")
    quantity_normalized = models.DecimalField(
        max_digits=18, decimal_places=4, null=True, blank=True,
        help_text="Normalized to SI or standard reporting unit"
    )
    unit_normalized = models.CharField(max_length=20, blank=True)

    # Emission calculation
    emission_factor = models.DecimalField(
        max_digits=12, decimal_places=6, null=True, blank=True,
        help_text="kg CO2e per unit (from DEFRA/EPA factors)"
    )
    emission_factor_source = models.CharField(max_length=100, blank=True, default='DEFRA 2023')
    co2e_kg = models.DecimalField(
        max_digits=14, decimal_places=4, null=True, blank=True,
        help_text="Calculated: quantity_normalized * emission_factor"
    )

    # Financial
    cost = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, blank=True, default='USD')

    # Temporal
    activity_date = models.DateField(null=True, blank=True)
    billing_period_start = models.DateField(null=True, blank=True)
    billing_period_end = models.DateField(null=True, blank=True)

    # Facility / organizational
    facility_code = models.CharField(max_length=50, blank=True)
    facility_name = models.CharField(max_length=255, blank=True)
    cost_center = models.CharField(max_length=50, blank=True)

    # Travel-specific
    origin = models.CharField(max_length=255, blank=True, help_text="For travel: departure location/airport code")
    destination = models.CharField(max_length=255, blank=True, help_text="For travel: arrival location/airport code")
    traveler_id = models.CharField(max_length=100, blank=True)

    # Review workflow
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    flag_reason = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reviewed_records'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"[Scope {self.scope}] {self.category} — {self.quantity} {self.unit} ({self.status})"

    class Meta:
        ordering = ['-activity_date', '-created_at']
        indexes = [
            models.Index(fields=['client', 'scope']),
            models.Index(fields=['client', 'status']),
            models.Index(fields=['ingestion_job']),
        ]


class AuditEntry(models.Model):
    """
    Immutable append-only audit trail for every state change on an EmissionRecord.
    Never update or delete these rows.
    """
    ACTION_CHOICES = [
        ('CREATED', 'Created'),
        ('FLAGGED', 'Flagged'),
        ('APPROVED', 'Approved'),
        ('LOCKED', 'Locked'),
        ('EDITED', 'Edited'),
        ('UNFLAGGED', 'Unflagged'),
    ]
    emission_record = models.ForeignKey(EmissionRecord, on_delete=models.CASCADE, related_name='audit_entries')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)
    diff = models.JSONField(default=dict, help_text="Field-level diff for EDITED actions")

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"{self.action} by {self.actor} at {self.timestamp}"
