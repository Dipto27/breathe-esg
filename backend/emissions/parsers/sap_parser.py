"""
SAP Fuel & Procurement Parser

Handles the MB51-style material movement flat file export from SAP.

SAP reality we're handling:
- Column headers are SAP field names (MBLNR, BUDAT, MATNR, etc.)
- Dates in YYYYMMDD format (SAP internal date format)
- SAP unit codes instead of SI (L, KL, G, TO, KG, M3, ST)
- German decimal separator in some configs (handled by trying both)
- Plant codes (WERKS) require lookup for human-readable facility names
- Material descriptions (MAKTX) are the key to identifying fuel vs. non-fuel

Scope 1 classification: We only ingest materials that map to combustion fuels.
Non-fuel procurement rows (spare parts, chemicals, office supplies) are skipped
and counted as ignored — this is a deliberate decision documented in TRADEOFFS.md.
"""
import csv
import io
from datetime import datetime
from decimal import Decimal, InvalidOperation


# SAP unit code → standard unit name
SAP_UNIT_MAP = {
    'L': 'L',
    'KL': 'L',  # KL = kiloliters → convert quantity * 1000
    'G': 'kg',  # grams → kg
    'KG': 'kg',
    'TO': 'tonne',  # metric ton
    'T': 'tonne',
    'M3': 'm3',
    'ST': 'unit',  # Stück = piece
    'EA': 'unit',
}

# SAP unit multipliers to normalize to standard unit
SAP_UNIT_MULTIPLIERS = {
    'KL': Decimal('1000'),  # KL → L
    'G': Decimal('0.001'),  # g → kg
}

# Material description keywords → fuel category
FUEL_KEYWORD_MAP = [
    (['diesel', 'gasoil', 'gas oil', 'hvgo', 'hsd'], 'fuel_diesel'),
    (['petrol', 'gasoline', 'unleaded', 'mogas', 'rbob'], 'fuel_petrol'),
    (['natural gas', 'lng', 'cng', 'methane', 'ng '], 'fuel_natural_gas'),
    (['lpg', 'propane', 'butane', 'autogas'], 'fuel_lpg'),
    (['fuel oil', 'furnace oil', 'heavy oil', 'light oil', 'kerosene', 'hfo', 'lfo'], 'fuel_other'),
]

# SAP plant code → facility name lookup table
# In a real deployment this would come from a client config table or API call
WERKS_LOOKUP = {
    '1000': 'Hamburg Plant',
    '1100': 'Berlin Plant',
    '2000': 'New York Office',
    '2100': 'Chicago Warehouse',
    '3000': 'Singapore Hub',
    'MAIN': 'Main Facility',
    'HQ': 'Headquarters',
}


def _parse_sap_date(date_str: str):
    """Parse SAP date format YYYYMMDD → Python date."""
    date_str = str(date_str).strip()
    for fmt in ('%Y%m%d', '%Y-%m-%d', '%d.%m.%Y', '%m/%d/%Y'):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


def _parse_decimal(val_str: str):
    """Parse decimal, handling German comma-as-decimal-separator."""
    val_str = str(val_str).strip()
    # If comma is likely decimal separator (European format): 1.234,56
    if ',' in val_str and '.' in val_str:
        # Remove thousand separator (.) then replace decimal comma
        val_str = val_str.replace('.', '').replace(',', '.')
    elif ',' in val_str and '.' not in val_str:
        val_str = val_str.replace(',', '.')
    try:
        return Decimal(val_str)
    except InvalidOperation:
        return None


def _classify_fuel(description: str):
    """Return fuel category based on material description, or None if not a fuel."""
    desc_lower = description.lower()
    for keywords, category in FUEL_KEYWORD_MAP:
        if any(kw in desc_lower for kw in keywords):
            return category
    return None


def parse_sap_csv(file_content: str):
    """
    Parse SAP MB51-style CSV export.
    
    Returns:
        records: list of normalized dicts ready for EmissionRecord creation
        errors: list of {row, message} dicts
        skipped: count of non-fuel rows intentionally ignored
    """
    records = []
    errors = []
    skipped = 0

    reader = csv.DictReader(io.StringIO(file_content))
    
    # Normalize headers — SAP exports sometimes have extra spaces
    fieldnames = [f.strip() for f in (reader.fieldnames or [])]

    for i, row in enumerate(reader, start=2):
        # Re-key with stripped names
        row = {k.strip(): v.strip() for k, v in row.items() if k}

        try:
            # Required fields
            doc_number = row.get('MBLNR', row.get('Document', f'ROW_{i}'))
            date_raw = row.get('BUDAT', row.get('PostingDate', ''))
            material_desc = row.get('MAKTX', row.get('MaterialDescription', ''))
            quantity_raw = row.get('MENGE', row.get('Quantity', ''))
            unit_raw = row.get('MEINS', row.get('Unit', '')).upper()
            plant_code = row.get('WERKS', row.get('Plant', ''))
            cost_center = row.get('KOSTL', row.get('CostCenter', ''))
            amount_raw = row.get('WRBTR', row.get('Amount', '0'))
            currency = row.get('WAERS', row.get('Currency', 'EUR'))

            # Classify fuel type — skip non-fuel rows
            category = _classify_fuel(material_desc)
            if not category:
                skipped += 1
                continue

            # Parse date
            activity_date = _parse_sap_date(date_raw)
            if not activity_date:
                errors.append({'row': i, 'message': f"Could not parse date: '{date_raw}'"})
                continue

            # Parse quantity
            quantity = _parse_decimal(quantity_raw)
            if quantity is None or quantity <= 0:
                errors.append({'row': i, 'message': f"Invalid quantity: '{quantity_raw}'"})
                continue

            # Normalize unit
            standard_unit = SAP_UNIT_MAP.get(unit_raw, unit_raw)
            multiplier = SAP_UNIT_MULTIPLIERS.get(unit_raw, Decimal('1'))
            quantity_normalized = quantity * multiplier

            # Facility lookup
            facility_name = WERKS_LOOKUP.get(plant_code, plant_code)

            records.append({
                'source_row_ref': doc_number,
                'scope': '1',
                'category': category,
                'activity_description': material_desc,
                'quantity': quantity,
                'unit': standard_unit,
                'quantity_normalized': quantity_normalized,
                'unit_normalized': standard_unit,
                'cost': _parse_decimal(amount_raw),
                'currency': currency,
                'activity_date': activity_date,
                'facility_code': plant_code,
                'facility_name': facility_name,
                'cost_center': cost_center,
            })

        except Exception as e:
            errors.append({'row': i, 'message': str(e)})

    return records, errors, skipped
