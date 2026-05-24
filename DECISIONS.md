# DECISIONS.md — Design Decisions Log

## Ambiguities Resolved

### 1. What subset of SAP data to handle?

**Chosen**: MB51 material movement style flat file export (CSV), handling fuel materials only.

**Why MB51**: SAP has dozens of export paths. Finance teams sending ESG data to sustainability analysts most commonly extract via MB51 (material movement list) or MM60 (materials analysis). MB51 is the most commonly exported transaction for fuel consumption tracking because it captures actual goods issues (movement type 261 = issue to cost center).

**Fuel identification**: We classify fuel by material description (MAKTX field) against a keyword map. We deliberately skip non-fuel procurement rows (spare parts, chemicals, office supplies). The alternative would be filtering by material group (MATKL), which requires the client to maintain a fuel material group configuration — too much per-client setup for a prototype.

**What we ignored**: 
- IDoc/XML format (complex parsing, requires SAP middleware knowledge)
- BAPI calls (requires live SAP connection, not feasible for a review prototype)
- MM60 Inventory management reports
- FI-CO cost center assignment reports
- Refrigerant/process emissions in SAP PM

**What I'd ask the PM**: "Which SAP transaction does the client's team currently use to pull fuel consumption? Is their SAP in German or English locale? Do they have a standard fuel material group we can filter on instead of description matching?"

---

### 2. Which utility data format to use?

**Chosen**: Portal CSV export (Urjanet-style / direct utility portal download).

**Why not PDF**: PDF bill parsing requires OCR and is layout-dependent. National Grid's PDF layout is different from ConEd's, which differs from PG&E's. A prototype that works for one utility breaks on another. PDFs also don't have machine-readable billing periods or meter-level breakdowns.

**Why not API**: Direct utility APIs exist (Green Button, Urjanet Connect), but each utility has different authentication, rate limits, and data formats. An API integration requires per-utility development work. The CSV export path is what facilities teams actually use day-to-day.

**What we handle**: Multi-meter per account (each row = one meter), estimated vs. actual reads (flagged), non-calendar billing periods, kWh as the primary quantity.

**What we ignored**: 
- Demand charges (we capture demand_kw but don't emit CO₂e from it)
- Time-of-use metering (no interval data, just billing period totals)
- Reactive power (KVAR) — irrelevant to carbon
- PDF bills

**What I'd ask the PM**: "Does the client export from a utility data aggregator like Urjanet or ENERGY STAR Portfolio Manager, or do they log into each utility portal separately? Are all meters in one country/grid, or multi-country?"

---

### 3. Which travel format and which scope 3 categories?

**Chosen**: Concur expense export CSV, covering air, hotel, car rental, and rail only.

**Why Concur**: Concur has ~70% enterprise market share. The assignment mentioned "Concur or Navan" — Navan is growing but Concur is still far more prevalent in large enterprises. Both export similarly formatted expense data.

**Category decisions**:
- Air travel (Airfare): Scope 3, Category 6 (Business travel) — emission factor per km
- Hotels: Scope 3, Category 6 — emission factor per room-night
- Car rental: Scope 3, Category 6 — emission factor per km (where available) or per trip
- Rail: Scope 3, Category 6 — emission factor per km

**What we ignored**:
- Meals (no emission basis in GHG Protocol)
- Parking (negligible, no standard factor)
- Conference fees
- Per-diem allowances
- Personal vehicle mileage (different from rental car — requires personal fuel type assumption)

**Distance handling**: When city_from/city_to are IATA airport codes, the distance is left for the analyst to see. We don't call a flight distance API in real-time (that's a production feature). When no distance is given, we use a per-trip average (2000km for air) and flag the record.

**What I'd ask the PM**: "Does the client use Concur's default expense types, or do they have a custom expense type hierarchy? Do they have a travel management company that could provide distance data alongside expense data?"

---

### 4. Multi-tenancy approach

**Chosen**: Foreign key per row on `EmissionRecord`, enforced in all API views.

**Why**: Schema-per-tenant adds operational complexity (migrations must run for each tenant). Row-level FK is sufficient for a prototype and up to moderate scale.

**What I'd ask the PM**: "How many client companies are expected? If it's <100, row-level FK is fine. At enterprise scale (1000+ clients with regulatory data), schema separation becomes important."

---

### 5. Emission factor source

**Chosen**: DEFRA 2023 (UK Department for Environment, Food & Rural Affairs).

**Why**: DEFRA publishes annually, is freely available, covers all three source types, and is the most widely accepted set of factors in EU corporate reporting. EPA (US) factors exist but DEFRA is more comprehensive for an international client.

**Caveat**: Electricity factors should ideally be location-based (different grid mixes per country). Our current implementation uses UK grid average for all electricity. In production, this would be parameterized per-meter based on facility location.

---

### 6. Review workflow state machine

States: PENDING → (FLAGGED | APPROVED) → LOCKED

**Why**: 
- PENDING: Default on ingest — hasn't been touched
- FLAGGED: Analyst identifies a concern (wrong quantity, suspicious spike, estimated read)
- APPROVED: Analyst confirms the record is correct and ready for audit
- LOCKED: Immutable state before sharing with auditors — no further changes

We deliberately did NOT implement: auto-approval, bulk approval without individual review, or AI-assisted anomaly detection. These are production features that would need PM sign-off on thresholds.
