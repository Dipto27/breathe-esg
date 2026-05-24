"""
Utility Electricity Data Parser

Handles CSV exports from utility portal systems (Urjanet-style, Enverus, or direct utility 
portal downloads from providers like ConEd, PG&E, National Grid).

Format choice: Portal CSV (as opposed to PDF bill or API)
Rationale: PDF parsing requires OCR and is brittle across utility bill layouts.
Direct API integration requires per-utility OAuth setup. The portal CSV export
is what facilities teams actually download — standardized enough to work with,
while realistic enough to have the quirks we handle here.

Key challenges handled:
- Billing periods that don't align to calendar months (12/15 → 01/18)
- Multiple meters per account (meter_id used as sub-key)
- Usage vs. demand charges (we capture both but emit on usage kWh only)
- Missing usage data when estimated reads are used (flagged, not errored)
"""
import csv
import io
from datetime import datetime
from decimal import Decimal, InvalidOperation


def _parse_date(val: str):
    val = str(val).strip()
    for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%d-%m-%Y', '%Y%m%d'):
        try:
            return datetime.strptime(val, fmt).date()
        except ValueError:
            continue
    return None


def _parse_decimal(val: str):
    val = str(val).strip().replace(',', '')
    try:
        return Decimal(val) if val else None
    except InvalidOperation:
        return None


def parse_utility_csv(file_content: str):
    """
    Parse utility portal CSV export.
    
    Expected columns (flexible matching):
      account_number, meter_id, service_address,
      billing_period_start, billing_period_end,
      usage_kwh, demand_kw, rate_schedule,
      amount_due, currency, read_type (ACTUAL|ESTIMATED)
    
    Returns:
        records, errors, skipped
    """
    records = []
    errors = []
    skipped = 0

    reader = csv.DictReader(io.StringIO(file_content))

    for i, row in enumerate(reader, start=2):
        row = {k.strip().lower().replace(' ', '_'): (v or '').strip() for k, v in row.items() if k}

        try:
            account = row.get('account_number', row.get('account', ''))
            meter_id = row.get('meter_id', row.get('meter', ''))
            address = row.get('service_address', row.get('address', ''))

            period_start = _parse_date(row.get('billing_period_start', row.get('period_start', '')))
            period_end = _parse_date(row.get('billing_period_end', row.get('period_end', '')))

            if not period_start or not period_end:
                errors.append({'row': i, 'message': 'Missing or invalid billing period dates'})
                continue

            usage_kwh = _parse_decimal(row.get('usage_kwh', row.get('kwh', row.get('consumption', ''))))
            if usage_kwh is None:
                errors.append({'row': i, 'message': 'Missing usage_kwh'})
                continue
            if usage_kwh < 0:
                errors.append({'row': i, 'message': f'Negative usage_kwh: {usage_kwh}'})
                continue

            read_type = row.get('read_type', row.get('reading_type', 'ACTUAL')).upper()
            amount = _parse_decimal(row.get('amount_due', row.get('amount', row.get('cost', ''))))
            currency = row.get('currency', 'USD').upper()
            rate_schedule = row.get('rate_schedule', row.get('tariff', ''))

            # Flag estimated reads — they're valid but analysts should know
            flag_reason = ''
            if read_type == 'ESTIMATED':
                flag_reason = 'Estimated meter read — verify with actual bill'

            description = f"Electricity — {address or meter_id or account} | {rate_schedule}"
            ref = f"{account}_{meter_id}_{period_start}"

            records.append({
                'source_row_ref': ref,
                'scope': '2',
                'category': 'electricity',
                'activity_description': description,
                'quantity': usage_kwh,
                'unit': 'kWh',
                'quantity_normalized': usage_kwh,  # kWh is already the standard unit
                'unit_normalized': 'kWh',
                'cost': amount,
                'currency': currency,
                'activity_date': period_end,  # Use end of billing period as the activity date
                'billing_period_start': period_start,
                'billing_period_end': period_end,
                'facility_code': meter_id or account,
                'facility_name': address,
                '_flag_reason': flag_reason,  # Internal flag to set status
            })

        except Exception as e:
            errors.append({'row': i, 'message': str(e)})

    return records, errors, skipped
