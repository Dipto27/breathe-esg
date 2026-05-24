"""
Corporate Travel Parser — Concur Expense Export

Handles CSV exports from SAP Concur expense management platform.

Format choice: Concur CSV export (vs. Navan API, manual entry)
Rationale: Concur has ~70% enterprise market share. Their standard expense report CSV
export is what travel managers actually send to ESG teams. Navan is growing but its
API requires OAuth and webhook setup — out of scope for initial ingestion.

Key challenges handled:
- Expense types need mapping to emission categories (Airfare≠Hotel≠Car)
- Distance is often missing — we note it as null (don't fabricate)  
- Airport codes vs. city names (airport codes get passed through; distance calc 
  would require a geo API which is a deliberate tradeoff — see TRADEOFFS.md)
- Multiple currencies (preserve original, don't convert)
- Hotel stays should be per-night not per-trip (handled via nights field)
"""
import csv
import io
from datetime import datetime
from decimal import Decimal, InvalidOperation


# Concur expense type strings → our emission categories
CONCUR_TYPE_MAP = {
    # Air travel
    'airfare': 'travel_air',
    'air': 'travel_air',
    'airline': 'travel_air',
    'flight': 'travel_air',
    'air travel': 'travel_air',
    # Hotel
    'hotel': 'travel_hotel',
    'lodging': 'travel_hotel',
    'accommodation': 'travel_hotel',
    'motel': 'travel_hotel',
    # Ground transport
    'car rental': 'travel_ground',
    'rental car': 'travel_ground',
    'taxi': 'travel_ground',
    'uber': 'travel_ground',
    'lyft': 'travel_ground',
    'ground transportation': 'travel_ground',
    'car': 'travel_ground',
    # Rail
    'train': 'travel_rail',
    'rail': 'travel_rail',
    'amtrak': 'travel_rail',
    'eurostar': 'travel_rail',
}

# Scope 3 sub-category for Concur types
CATEGORY_TO_SCOPE3 = {
    'travel_air': '3',
    'travel_hotel': '3',
    'travel_ground': '3',
    'travel_rail': '3',
}


def _parse_date(val: str):
    val = str(val).strip()
    for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%m-%d-%Y'):
        try:
            return datetime.strptime(val, fmt).date()
        except ValueError:
            continue
    return None


def _parse_decimal(val: str):
    val = str(val).strip().replace(',', '').replace('$', '').replace('€', '').replace('£', '')
    try:
        return Decimal(val) if val else None
    except InvalidOperation:
        return None


def _classify_expense_type(expense_type_str: str):
    """Map Concur expense type string to emission category."""
    lower = expense_type_str.lower().strip()
    for key, category in CONCUR_TYPE_MAP.items():
        if key in lower:
            return category
    return None


def parse_travel_csv(file_content: str):
    """
    Parse Concur expense report CSV export.
    
    Expected columns (flexible matching):
      report_id, employee_id, expense_date, expense_type,
      vendor, city_from (or origin), city_to (or destination),
      distance_km (optional), nights (for hotel),
      amount, currency, trip_purpose, project_code
    
    Returns:
        records, errors, skipped
    """
    records = []
    errors = []
    skipped = 0

    reader = csv.DictReader(io.StringIO(file_content))

    for i, row in enumerate(reader, start=2):
        row = {k.strip().lower().replace(' ', '_'): v.strip() for k, v in row.items() if k}

        try:
            report_id = row.get('report_id', row.get('report', f'ROW_{i}'))
            employee_id = row.get('employee_id', row.get('employee', ''))
            expense_date_raw = row.get('expense_date', row.get('date', ''))
            expense_type_raw = row.get('expense_type', row.get('type', row.get('category', '')))

            expense_date = _parse_date(expense_date_raw)
            if not expense_date:
                errors.append({'row': i, 'message': f"Invalid expense date: '{expense_date_raw}'"})
                continue

            category = _classify_expense_type(expense_type_raw)
            if not category:
                skipped += 1
                continue  # Non-travel expense (meals, parking, etc.) — skip per TRADEOFFS

            vendor = row.get('vendor', '')
            origin = row.get('city_from', row.get('origin', row.get('departure', '')))
            destination = row.get('city_to', row.get('destination', row.get('arrival', '')))
            distance_km = _parse_decimal(row.get('distance_km', row.get('distance', '')))
            nights = _parse_decimal(row.get('nights', row.get('night', '1' if category == 'travel_hotel' else '')))
            amount = _parse_decimal(row.get('amount', row.get('total', row.get('cost', ''))))
            currency = row.get('currency', row.get('currency_code', 'USD')).upper()
            project_code = row.get('project_code', row.get('project', ''))

            # Determine quantity and unit
            if category == 'travel_hotel':
                quantity = nights if nights and nights > 0 else Decimal('1')
                unit = 'nights'
            elif distance_km and distance_km > 0:
                quantity = distance_km
                unit = 'km'
            else:
                # For air travel without distance: use a placeholder of 1 trip
                # Emission factor handles average per-trip; noted in flag_reason
                quantity = Decimal('1')
                unit = 'trip'

            description_parts = [expense_type_raw]
            if origin and destination:
                description_parts.append(f"{origin} → {destination}")
            elif vendor:
                description_parts.append(vendor)
            description = ' | '.join(filter(None, description_parts))

            flag_reason = ''
            if unit == 'trip':
                flag_reason = 'Distance not provided — emission calculated using average per-trip factor'

            records.append({
                'source_row_ref': f"{report_id}_{i}",
                'scope': '3',
                'category': category,
                'activity_description': description,
                'quantity': quantity,
                'unit': unit,
                'quantity_normalized': quantity,
                'unit_normalized': unit,
                'cost': amount,
                'currency': currency,
                'activity_date': expense_date,
                'origin': origin,
                'destination': destination,
                'traveler_id': employee_id,
                'cost_center': project_code,
                '_flag_reason': flag_reason,
            })

        except Exception as e:
            errors.append({'row': i, 'message': str(e)})

    return records, errors, skipped
