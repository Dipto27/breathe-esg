"""
Unit tests for parsers and emission factor calculations.
Run: python manage.py test emissions
"""
from django.test import TestCase
from decimal import Decimal
from emissions.parsers.sap_parser import parse_sap_csv
from emissions.parsers.utility_parser import parse_utility_csv
from emissions.parsers.travel_parser import parse_travel_csv
from emissions.normalizers.emission_factors import calculate_co2e


SAP_SAMPLE = """MBLNR,BUDAT,MATNR,MAKTX,MENGE,MEINS,WERKS,KOSTL,WRBTR,WAERS
4900001234,20240115,DIESEL001,Diesel HSD,12500,L,1000,CC-MAINT,18750.00,EUR
4900001289,20240128,OFFICE001,Office Paper,500,KG,1000,CC-ADM,250.00,EUR
4900001310,20240210,NATGAS001,Natural Gas,4200,M3,1000,CC-HEAT,5040.00,EUR
9900001999,BAD_DATE,DIESEL001,Diesel HSD,1000,L,1000,CC-MAINT,1500.00,EUR
"""

UTILITY_SAMPLE = """account_number,meter_id,service_address,billing_period_start,billing_period_end,usage_kwh,amount_due,currency,read_type
ACC-001,MTR-01,Hamburg Plant,2024-01-01,2024-01-31,50000,7500.00,EUR,ACTUAL
ACC-001,MTR-02,Berlin Office,2024-01-01,2024-01-31,12000,1800.00,EUR,ESTIMATED
ACC-002,MTR-03,Bad Data,,,,EUR,ACTUAL
"""

TRAVEL_SAMPLE = """report_id,employee_id,expense_date,expense_type,vendor,city_from,city_to,distance_km,nights,amount,currency,project_code
CONC-R001,EMP-01,2024-01-10,Airfare,United,JFK,LHR,5570,,1850.00,USD,PROJ-A
CONC-R001,EMP-01,2024-01-14,Hotel,Marriott,,London,,4,1200.00,GBP,PROJ-A
CONC-R002,EMP-02,2024-01-22,Meals,Restaurant,,,,1,45.00,USD,PROJ-B
CONC-R003,EMP-03,bad_date,Airfare,Delta,ORD,ATL,1400,,800.00,USD,PROJ-C
"""


class SAPParserTest(TestCase):
    def test_fuel_rows_ingested(self):
        records, errors, skipped = parse_sap_csv(SAP_SAMPLE)
        # Diesel and natural gas should be ingested
        self.assertEqual(len(records), 2)
        categories = {r['category'] for r in records}
        self.assertIn('fuel_diesel', categories)
        self.assertIn('fuel_natural_gas', categories)

    def test_non_fuel_skipped(self):
        records, errors, skipped = parse_sap_csv(SAP_SAMPLE)
        self.assertEqual(skipped, 1)  # Office Paper skipped

    def test_bad_date_creates_error(self):
        records, errors, skipped = parse_sap_csv(SAP_SAMPLE)
        self.assertEqual(len(errors), 1)
        self.assertIn('date', errors[0]['message'].lower())

    def test_scope_is_1(self):
        records, errors, skipped = parse_sap_csv(SAP_SAMPLE)
        for r in records:
            self.assertEqual(r['scope'], '1')

    def test_sap_date_parsed(self):
        records, errors, skipped = parse_sap_csv(SAP_SAMPLE)
        diesel = next(r for r in records if r['category'] == 'fuel_diesel')
        from datetime import date
        self.assertEqual(diesel['activity_date'], date(2024, 1, 15))

    def test_quantity_preserved(self):
        records, errors, skipped = parse_sap_csv(SAP_SAMPLE)
        diesel = next(r for r in records if r['category'] == 'fuel_diesel')
        self.assertEqual(diesel['quantity'], Decimal('12500'))
        self.assertEqual(diesel['unit'], 'L')


class UtilityParserTest(TestCase):
    def test_actual_read_ingested(self):
        records, errors, skipped = parse_utility_csv(UTILITY_SAMPLE)
        actual = [r for r in records if 'Estimated' not in r.get('_flag_reason', '')]
        self.assertGreater(len(actual), 0)

    def test_estimated_read_flagged(self):
        records, errors, skipped = parse_utility_csv(UTILITY_SAMPLE)
        estimated = [r for r in records if r.get('_flag_reason')]
        self.assertEqual(len(estimated), 1)
        self.assertIn('Estimated', estimated[0]['_flag_reason'])

    def test_scope_is_2(self):
        records, errors, skipped = parse_utility_csv(UTILITY_SAMPLE)
        for r in records:
            self.assertEqual(r['scope'], '2')

    def test_bad_row_creates_error(self):
        records, errors, skipped = parse_utility_csv(UTILITY_SAMPLE)
        self.assertEqual(len(errors), 1)

    def test_kwh_as_unit(self):
        records, errors, skipped = parse_utility_csv(UTILITY_SAMPLE)
        for r in records:
            self.assertEqual(r['unit'], 'kWh')


class TravelParserTest(TestCase):
    def test_airfare_and_hotel_ingested(self):
        records, errors, skipped = parse_travel_csv(TRAVEL_SAMPLE)
        categories = {r['category'] for r in records}
        self.assertIn('travel_air', categories)
        self.assertIn('travel_hotel', categories)

    def test_meals_skipped(self):
        records, errors, skipped = parse_travel_csv(TRAVEL_SAMPLE)
        self.assertEqual(skipped, 1)  # Meals skipped

    def test_bad_date_creates_error(self):
        records, errors, skipped = parse_travel_csv(TRAVEL_SAMPLE)
        self.assertEqual(len(errors), 1)

    def test_hotel_unit_is_nights(self):
        records, errors, skipped = parse_travel_csv(TRAVEL_SAMPLE)
        hotel = next(r for r in records if r['category'] == 'travel_hotel')
        self.assertEqual(hotel['unit'], 'nights')
        self.assertEqual(hotel['quantity'], Decimal('4'))

    def test_scope_is_3(self):
        records, errors, skipped = parse_travel_csv(TRAVEL_SAMPLE)
        for r in records:
            self.assertEqual(r['scope'], '3')


class EmissionFactorTest(TestCase):
    def test_diesel_calculation(self):
        co2e, factor, notes = calculate_co2e('fuel_diesel', Decimal('1000'), 'L')
        self.assertIsNotNone(co2e)
        # 1000L * 2.5163 = 2516.3 kg CO2e
        self.assertAlmostEqual(float(co2e), 2516.3, places=0)

    def test_electricity_calculation(self):
        co2e, factor, notes = calculate_co2e('electricity', Decimal('10000'), 'kWh')
        self.assertIsNotNone(co2e)
        # 10000 * 0.23314 = 2331.4 kg CO2e
        self.assertAlmostEqual(float(co2e), 2331.4, places=0)

    def test_trip_unit_uses_average_distance(self):
        co2e_trip, _, _ = calculate_co2e('travel_air', Decimal('1'), 'trip')
        co2e_km, _, _ = calculate_co2e('travel_air', Decimal('2000'), 'km')
        # Should be equal (trip = 2000km average)
        self.assertAlmostEqual(float(co2e_trip), float(co2e_km), places=1)

    def test_unknown_category_returns_none(self):
        co2e, factor, notes = calculate_co2e('unknown_category', Decimal('100'), 'units')
        self.assertIsNone(co2e)
        self.assertIsNone(factor)
