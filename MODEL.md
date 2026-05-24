# MODEL.md — Data Model Documentation

## Overview

The data model is designed around a single canonical normalized record type (`EmissionRecord`) that can represent activity data regardless of its source. Every design decision prioritizes auditability, traceability, and multi-tenant isolation.

---

## Core Design Principles

### 1. Single normalized table, not per-source tables

We chose a single `EmissionRecord` table rather than separate tables per source (SapRecord, UtilityRecord, TravelRecord). 

**Why**: An analyst reviewing data doesn't care where it came from — they care about scope, quantity, and CO₂e. A unified table enables cross-source queries (total Scope 1 CO₂e, all flagged records, etc.) without joins. Source-specific fields (origin, destination for travel; billing_period for utility; facility_code for SAP) are nullable columns on the same table.

**Tradeoff**: Some source-specific columns are always null for other source types. We accepted this for query simplicity.

### 2. Multi-tenancy via Foreign Key, not schema separation

Every record has a `client_id` FK. All API views filter by `client_id` through `UserClientMembership`. 

**Why**: Schema-per-tenant is operationally complex. Row-level FK isolation is simpler to reason about and sufficient at this scale. If this grew to hundreds of clients with millions of rows each, schema-per-tenant or partitioning would become necessary.

### 3. Immutable audit log (AuditEntry)

`AuditEntry` rows are never updated or deleted. Every state change to `EmissionRecord` creates a new entry.

**Why**: This is a legal/compliance requirement for pre-audit data. If a record is approved and later found incorrect, the audit trail must show who approved it and when, even after correction. Using Django's `auto_now_add=True` prevents backdating.

### 4. Preserve original quantities alongside normalized

`EmissionRecord` stores both `quantity`/`unit` (original from source) and `quantity_normalized`/`unit_normalized` (after conversion). The emission factor is applied to `quantity_normalized`.

**Why**: If an SAP export contains liters and we normalize to m³ for natural gas, the analyst should see the original liters they recognize from their ERP, not the converted value. This prevents "where did this number come from?" questions during audit review.

---

## Entity Relationships

```
Client
  ├── UserClientMembership (user <-> client, with role)
  ├── DataSource (SAP | UTILITY | TRAVEL, one per meter/feed)
  │     └── IngestionJob (one per file upload)
  │           └── EmissionRecord (N records per job)
  │                 └── AuditEntry (append-only log per record)
  └── EmissionRecord (direct FK for fast filtering)
```

---

## EmissionRecord Fields

### Provenance Fields
| Field | Type | Purpose |
|-------|------|---------|
| `client` | FK | Multi-tenant isolation |
| `ingestion_job` | FK | Links back to raw file |
| `source_type` | Char | SAP \| UTILITY \| TRAVEL |
| `source_row_ref` | Char | Document/row ID in source system |

### Scope Classification
| Field | Type | Values |
|-------|------|--------|
| `scope` | Char | 1, 2, 3 |
| `category` | Char | fuel_diesel, fuel_petrol, fuel_natural_gas, fuel_lpg, fuel_other, electricity, travel_air, travel_hotel, travel_ground, travel_rail |

**Scope assignment logic:**
- Scope 1: All SAP fuel records (direct combustion)
- Scope 2: All utility electricity records (market-based or location-based)
- Scope 3: All travel records (upstream/downstream value chain)

### Quantity Fields
| Field | Type | Notes |
|-------|------|-------|
| `quantity` | Decimal(18,4) | Original value from source |
| `unit` | Char | Original unit (L, kWh, km, nights) |
| `quantity_normalized` | Decimal(18,4) | After unit conversion |
| `unit_normalized` | Char | Standard unit for emission factor |

### Emission Calculation
| Field | Type | Notes |
|-------|------|-------|
| `emission_factor` | Decimal(12,6) | kg CO₂e per unit_normalized |
| `emission_factor_source` | Char | "DEFRA 2023" |
| `co2e_kg` | Decimal(14,4) | quantity_normalized × emission_factor |

### Review Workflow
| Status | Meaning |
|--------|---------|
| PENDING | Ingested, not yet reviewed |
| FLAGGED | Analyst flagged for investigation |
| APPROVED | Analyst confirmed correct |
| LOCKED | Locked for audit (immutable) |

---

## Source-Specific Fields

### SAP-specific
- `facility_code`: WERKS (SAP plant code)
- `facility_name`: Looked up from plant code table
- `cost_center`: KOSTL

### Utility-specific
- `billing_period_start` / `billing_period_end`: Billing months
- `facility_code`: Meter ID
- `facility_name`: Service address

### Travel-specific
- `origin`: Departure city/airport code
- `destination`: Arrival city/airport code
- `traveler_id`: Employee ID
- `cost_center`: Project/trip code

---

## Emission Factors

Source: **DEFRA 2023 GHG Conversion Factors for Company Reporting**

| Category | Factor | Unit |
|----------|--------|------|
| Diesel | 2.5163 kg CO₂e | per litre |
| Petrol | 2.1662 kg CO₂e | per litre |
| Natural Gas | 2.0407 kg CO₂e | per m³ |
| LPG | 1.5557 kg CO₂e | per litre |
| Electricity (UK grid avg) | 0.23314 kg CO₂e | per kWh |
| Air travel | 0.2553 kg CO₂e | per km |
| Hotel | 20.8 kg CO₂e | per room-night |
| Ground transport | 0.1589 kg CO₂e | per km |
| Rail | 0.0355 kg CO₂e | per km |

In production: electricity factor would be location-based (different grids per country) or market-based (per supplier renewable certificate). Travel factors would be split by aircraft class and cabin class.
