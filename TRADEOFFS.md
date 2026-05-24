# TRADEOFFS.md — What We Deliberately Did Not Build

## Three things we chose not to build, and why.

---

### 1. Distance-based emission calculation for flights using live geo API

**What we didn't build**: Automatic calculation of flight distances by calling a great-circle distance API (like the OpenFlights database or AviationStack) when IATA airport codes are available in the Concur export.

**What we built instead**: We store the origin and destination airport codes, flag records where distance was not provided, and use a per-trip average (2000km) with a clear analyst-visible warning.

**Why we skipped it**:

1. **Data quality concern**: Great-circle distance (direct path) underestimates actual flight distance by 8-15% due to routing, air traffic control, and jet stream effects. DEFRA's own methodology uses a 1.08 uplift factor on great-circle to account for this. Getting the distance "automatically" from codes without applying the right uplift gives analysts false precision.

2. **The call is a network dependency**: A real-time geo API call during ingestion creates failure modes. If the API is down, the ingestion fails or produces silent errors. The design choice to flag and let the analyst verify preserves correctness over convenience.

3. **Analysts should review these**: A record where distance is unknown is exactly the kind of thing an analyst should see and decide about — not something the system should silently estimate away. We make it visible via FLAGGED status.

**Production path**: Build a distance lookup table from OpenFlights (free, ~70,000 routes) loaded at deploy time. No external API call needed. Apply DEFRA uplift factor. This is a day-2 feature, not day-0.

---

### 2. Location-based vs. market-based electricity emission factors

**What we didn't build**: Per-facility electricity emission factors based on grid location (country/region), or the ability to use market-based factors (supplier-specific emission intensity from renewable energy certificates).

**What we built instead**: A single global factor (DEFRA 2023 UK grid average: 0.23314 kg CO₂e/kWh) applied to all electricity records.

**Why we skipped it**:

1. **Two different accounting approaches, significant consequences**: Location-based uses average grid emissions (what electrons actually flow through the meter). Market-based lets companies claim lower factors when they purchase RECs or have PPAs. The GHG Protocol allows both but treats them differently. Choosing the wrong one for a client's disclosure methodology is not a system concern — it's a methodology decision that must come from the client's CFO and ESG lead.

2. **Requires per-meter location data**: The utility CSV may not include country/region. We'd need the client to maintain a facility→location mapping. Without reliable facility locations, applying different factors creates a worse result than a consistent global factor.

3. **Scope 2 is the smallest emitter in this dataset**: In our sample data, Scope 2 is ~170 tCO₂e vs. Scope 1 at ~85 tCO₂e and Scope 3 at ~5 tCO₂e. The calculation error from using the wrong electricity factor is meaningful but not dominant. Getting it right matters, but it's a precision issue, not a structural one.

**Production path**: Add a `grid_region` field to `DataSource` for utility sources. Maintain an `ElectricityEmissionFactor` table keyed by region + year. On ingest, look up the right factor. For market-based, allow uploading supplier emission intensity certificates.

---

### 3. Bulk approval and audit lock workflow

**What we didn't build**: Batch approval (select all approved records and lock them in one click), workflow stages beyond the current 4-state model, email notifications to approvers, or integration with DocuSign/approval software for the final sign-off.

**What we built instead**: Individual record approve/flag actions with a full audit trail per record. No locking mechanism is implemented yet (LOCKED status exists in the model but has no trigger).

**Why we skipped it**:

1. **"Sign off before it goes to auditors" requires understanding the sign-off process**: Different companies handle audit preparation differently. Some need a senior manager's digital signature. Some use a separate GHG audit software (e.g., Persefoni, Watershed). Building a bulk-lock workflow without knowing how this integrates into their existing process risks building the wrong thing.

2. **Individual review is the point**: The assignment says "let our analysts review and sign off before it goes to auditors." The natural unit is the individual record, not the batch. Bulk approval without individual review defeats the purpose. Building bulk approval before the individual flow was solid would be premature.

3. **Notifications require email infrastructure**: Adding email notifications requires a transactional email service (SendGrid, SES), templates, unsubscribe handling, and preference management. That's a full feature, not a UI button.

**Production path**: Add a `SignOffBatch` model that groups approved records and captures a manager-level approval with timestamp + digital attestation (could be password re-authentication for weight of signature). Add a LOCKED transition triggered by the batch sign-off. Add email notifications via Celery + SendGrid when records are assigned for review.
