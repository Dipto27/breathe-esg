"""
Emission factor lookup and CO2e calculation.

Factors sourced from DEFRA 2023 GHG Conversion Factors for Company Reporting.
These are published annually by the UK Department for Environment, Food & Rural Affairs
and are the most commonly used factors in corporate ESG reporting.

Units: kg CO2e per unit of activity
"""
from decimal import Decimal

# DEFRA 2023 emission factors (kg CO2e per unit)
# Source: https://www.gov.uk/government/publications/greenhouse-gas-reporting-conversion-factors-2023
EMISSION_FACTORS = {
    # Scope 1 — fuel combustion (kg CO2e per litre unless noted)
    'fuel_diesel': Decimal('2.5163'),    # per litre
    'fuel_petrol': Decimal('2.1662'),    # per litre
    'fuel_natural_gas': Decimal('2.0407'),  # per m3
    'fuel_lpg': Decimal('1.5557'),       # per litre
    'fuel_other': Decimal('2.7537'),     # per litre (fuel oil)

    # Scope 2 — electricity (kg CO2e per kWh)
    # Using UK grid average; in production would use location-based or market-based factor
    'electricity': Decimal('0.23314'),   # UK average 2023

    # Scope 3 — travel (kg CO2e per unit)
    'travel_air': Decimal('0.2553'),     # per km, average haul, economy class
    'travel_hotel': Decimal('20.8'),     # per room-night (UK hotels, DEFRA 2023)
    'travel_ground': Decimal('0.1589'),  # per km (average car rental, petrol)
    'travel_rail': Decimal('0.0355'),    # per km (national rail UK average)
}

# Unit expected for each category's emission factor
FACTOR_UNITS = {
    'fuel_diesel': 'L',
    'fuel_petrol': 'L',
    'fuel_natural_gas': 'm3',
    'fuel_lpg': 'L',
    'fuel_other': 'L',
    'electricity': 'kWh',
    'travel_air': 'km',
    'travel_hotel': 'nights',
    'travel_ground': 'km',
    'travel_rail': 'km',
}

# For "trip" unit (no distance), use average distances
AVERAGE_TRIP_DISTANCES = {
    'travel_air': Decimal('2000'),    # km — average business flight
    'travel_ground': Decimal('50'),   # km — average car rental trip
    'travel_rail': Decimal('150'),    # km — average rail trip
}


def calculate_co2e(category: str, quantity_normalized, unit: str):
    """
    Calculate kg CO2e for a given category, quantity, and unit.
    Returns (co2e_kg, emission_factor, notes)
    """
    factor = EMISSION_FACTORS.get(category)
    if factor is None:
        return None, None, f"No emission factor for category: {category}"

    qty = Decimal(str(quantity_normalized))

    # Handle "trip" unit — use average distance
    notes = ''
    if unit == 'trip':
        avg_dist = AVERAGE_TRIP_DISTANCES.get(category, Decimal('1'))
        qty = qty * avg_dist
        notes = f'Used average distance of {avg_dist}km per trip'

    co2e_kg = qty * factor
    return co2e_kg, factor, notes
