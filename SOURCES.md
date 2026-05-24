# SOURCES.md — Source Format Research

## What we learned about each data source

---

## 1. SAP — Fuel & Procurement

### Real-world format researched

SAP produces several export formats depending on the transaction and configuration:

- **IDocs (Intermediate Documents)**: SAP's native data interchange format. XML or flat-file segments. Used for EDI and system-to-system transfers. Contains every field but requires SAP middleware (XI/PI or PO) to extract. Most ESG analysts do not have this access.

- **BAPI/RFC exports**: Remote Function Calls that return structured data. Require SAP developer access and a running SAP instance. Not realistic for an analyst-driven ESG workflow.

- **SE16/SQVI/MB51 flat file exports**: Transaction-level exports that finance and warehouse analysts actually use. Downloaded as `.txt` or `.xlsx` files. These are what get emailed to ESG teams. **This is what we implemented.**

- **OData services**: SAP's modern REST-ish API layer. Requires configuration by SAP Basis team. More realistic than IDocs for new integrations, but requires client-side setup.

### What we learned

SAP's MB51 (Material Document List) exports contain these field names in German in European SAP instances:

| SAP Field | German Label | English Meaning |
|-----------|-------------|-----------------|
| MBLNR | Materialbelegnnummer | Material document number |
| BUDAT | Buchungsdatum | Posting date (YYYYMMDD) |
| MATNR | Materialnummer | Material number |
| MAKTX | Materialkurztext | Material short description |
| MENGE | Menge | Quantity |
| MEINS | Basismengeneinheit | Base unit of measure |
| WERKS | Werk | Plant code |
| KOSTL | Kostenstelle | Cost center |
| WRBTR | Betrag in Belegwährung | Amount in document currency |
| WAERS | Währungsschlüssel | Currency key |

**Date format**: YYYYMMDD (SAP internal format, no separators) — we parse this specifically.

**Decimal format**: German configurations use period as thousands separator and comma as decimal separator (e.g., `1.234,56` = 1234.56). We handle both European and American formats.

**Unit codes**: SAP uses its own unit codes (L for liters, KL for kiloliters, G for grams, TO for metric tons, M3 for cubic meters). We map these to standard units.

### Sample data design choices

Our sample data uses:
- German plant codes (1000, 1100 = Hamburg, Berlin plants — realistic for a German enterprise)
- SAP date format (YYYYMMDD)
- Mixed materials (diesel, natural gas, petrol) with real SAP-style material numbers
- Real German-style cost center codes

### What would break in real deployment

1. **Plant code lookup table**: Real deployments have hundreds of plant codes. Our hardcoded WERKS_LOOKUP table would need to be loaded from a client-provided mapping file or from SAP's T001W table.

2. **Material group filtering**: Instead of description matching for fuel identification, production would use SAP material group (MATKL) field, which the client's SAP team can configure as a fuel group.

3. **Movement type filtering**: MB51 contains all material movements. We should filter to movement type 261 (goods issue to cost center) and exclude 261/R (reversals) rather than relying on positive quantity.

4. **Multi-language**: SAP instances in Asia may have different character encodings. We handle UTF-8-BOM (Excel default) but not Shift-JIS or GB18030.

---

## 2. Utility Data — Electricity

### Real-world format researched

Electricity data reaches ESG teams through several paths:

- **PDF bills**: Most common in the real world, least useful for data processing. Paper format varies by utility. Contains meter readings, usage, demand, rate schedule, charges.

- **Portal CSV exports**: Utility portals (ConEd, National Grid, PG&E, etc.) allow bulk export of billing history as CSV. This is what facilities managers actually download for ESG reporting. Structure is more consistent than PDFs.

- **Urjanet / Arcadia / UtilityAPI**: Aggregator services that connect to hundreds of utility portals via credential-sharing or OAuth and normalize the data. This is the professional approach but costs money per meter per month.

- **Green Button Connect**: A US standard for utility data access (XML format). Supported by ~60% of US utilities. More structured but still requires per-utility enrollment.

- **ENERGY STAR Portfolio Manager**: EPA tool that aggregates utility data. Most US commercial building owners already use it. Exports in a standard format.

**We implemented**: Portal CSV export, because it's the realistic analyst-facing artifact. We modeled the format on what Urjanet-normalized data looks like, since that's what companies using a data aggregator would see.

### What we learned

Key challenges with real utility data:
- **Billing periods don't align with calendar months**: A meter might bill on the 15th, meaning January data runs Dec 15 – Jan 14. We store both billing_period_start and billing_period_end and use period_end as the activity_date.
- **Estimated reads**: When a meter reader can't access the premises, the utility estimates usage based on prior periods. These should be flagged for analyst attention.
- **Multiple meters per account**: Large facilities have sub-metering. Each meter = one row. We use meter_id as the sub-key.
- **Multi-currency**: International clients pay in local currency. We preserve original currency.
- **Demand charges**: Utilities charge for peak demand (kW) separately from consumption (kWh). We capture demand_kw but only calculate CO₂e from kWh usage.

### Sample data design choices

Our sample data reflects:
- Meters across different facilities (Hamburg, Berlin, New York)
- One estimated read (flagged on ingestion)
- Non-calendar billing periods (we use billing_period_start/end)
- Different currencies (EUR, USD)

### What would break in real deployment

1. **Negative usage**: Some meter exports show negative kWh when a facility has solar generation that feeds back to the grid. Our parser rejects negatives — production would need to handle net metering.

2. **Unit variation**: Most EU utility exports use kWh, but some industrial meters export MWh or kJ. We only handle kWh currently.

3. **Account number changes**: When utilities consolidate accounts or replace meters, historical data may have different account numbers for the same physical facility. Manual mapping required.

4. **Distribution losses**: UK's location-based Scope 2 factors include transmission and distribution losses. Market-based factors may not. Our factor (DEFRA 0.23314) includes T&D losses.

---

## 3. Corporate Travel — Concur

### Real-world format researched

Corporate travel data reaches ESG teams via:

- **Concur expense export**: SAP Concur is used by ~70% of Fortune 500 for expense management. The standard expense report export is a flat CSV that can be exported by travel managers. This is the realistic artifact.

- **Navan (formerly TripActions) API**: Navan has a REST API with OAuth. More modern, but smaller market share. Requires API credentials from the corporate travel team.

- **Travel Management Company (TMC) data**: Companies using a TMC (AmEx GBT, BCD, CWT) can request an emission report directly. These are often annual exports, not real-time.

- **Credit card transaction feeds**: Visa/Mastercard commercial data programs provide transaction-level data with merchant category codes (MCC). Less structured than expense reports but comprehensive.

**We implemented**: Concur CSV export, because it's realistic, contains the right fields, and doesn't require API authentication to get started.

### What we learned

Concur's default expense types relevant to scope 3:
- Airfare / Air Travel → `travel_air`
- Hotel / Lodging / Accommodation → `travel_hotel`  
- Car Rental / Rental Car → `travel_ground`
- Taxi / Uber / Lyft / Ground Transportation → `travel_ground`
- Train / Rail / Amtrak / Eurostar → `travel_rail`

Non-emission expense types we deliberately skip:
- Meals / Per Diem (no GHG Protocol basis)
- Parking (negligible, no standard factor)
- Conference fees
- Phone / Internet

**Key insight on distances**: Concur does not reliably provide flight distances. Companies using Concur + a TMC may get route data. Without TMC, you have origin/destination city or airport codes only. The distance must either be looked up or estimated.

**Hotels — nights vs. days**: Concur hotel expense records represent the total bill for a stay, not per-night. The "nights" field is calculated from check-in/check-out dates in the expense report. Some Concur configurations don't export this. We fall back to 1 night when missing, which understates the emission.

### Sample data design choices

Our sample data:
- Includes IATA airport codes for origin/destination (JFK, LHR, FRA, SIN, ORD, AMS) — realistic for international business travel
- Shows one record with missing distance (flagged automatically)
- Shows hotel with 4-night stay
- Shows car rental with distance provided
- Covers multiple employees (EMP-0042, EMP-0078, EMP-0121) and projects

### What would break in real deployment

1. **Expense type customization**: Large enterprises customize Concur expense types. "Air Travel (International)", "Air Travel (Domestic)", "Train Europe" are all non-standard types that our keyword matching might miss. Production would need a client-specific type mapping table.

2. **Multi-leg trips**: A business trip JFK→LHR→FRA might be booked as one expense or three. Without trip/leg structure, we can't distinguish. Concur's standard export doesn't have leg-level data unless using Concur Travel (the booking module, not just expense).

3. **Class of service**: DEFRA has separate emission factors for economy, premium economy, business, and first class. Concur may have ticket class if the traveler entered it. We use economy average for all. Overstatement for economy travelers, understatement for business class.

4. **Currency for emission factor**: Our emission factor (kg CO₂e/km or per night) is the same regardless of currency. The cost field uses original currency, which we don't convert. For emission intensity analysis (CO₂e per dollar spent), currency conversion would be needed.
