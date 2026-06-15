"""
Integration tests for Trip API endpoints and PDF generation.

Tests use the DRF test client and a real SQLite database.
"""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Driver
from apps.hos.models import DutyStatusLog
from apps.trips.models import Trip, TripStop


class TripAPITestCase(TestCase):
    """Base class with common setup for trip API tests."""

    def setUp(self):
        self.client = APIClient()
        self.driver = Driver.objects.create_user(
            username='testdriver',
            password='testpass123',
            first_name='Test',
            last_name='Driver',
            license_number='CDL-TEST',
            carrier_name='Test Carrier LLC',
            carrier_address='123 Test St',
            cycle_type='70_8',
            truck_number='TRK-001',
        )
        # Authenticate the test client via JWT
        token = RefreshToken.for_user(self.driver)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')

    def _create_trip(self, **overrides):
        """Helper to create a Trip object in the database."""
        now = timezone.now()
        defaults = {
            'driver': self.driver,
            'status': 'completed',
            'current_location': 'New York, NY',
            'current_lat': Decimal('40.712800'),
            'current_lon': Decimal('-74.006000'),
            'pickup_location': 'Philadelphia, PA',
            'pickup_lat': Decimal('39.952600'),
            'pickup_lon': Decimal('-75.165200'),
            'dropoff_location': 'Atlanta, GA',
            'dropoff_lat': Decimal('33.749000'),
            'dropoff_lon': Decimal('-84.388000'),
            'current_cycle_used': Decimal('20.00'),
            'total_distance_miles': Decimal('874.0'),
            'estimated_duration_hours': Decimal('14.50'),
            'total_trip_days': 2,
            'total_driving_hours': Decimal('14.50'),
        }
        defaults.update(overrides)
        return Trip.objects.create(**defaults)

    def _create_duty_logs(self, trip):
        """Create sample duty log entries for a trip."""
        now = timezone.now().replace(hour=6, minute=0, second=0, microsecond=0)
        logs = [
            DutyStatusLog(
                driver=self.driver,
                trip=trip,
                status='on_duty_not_driving',
                start_time=now,
                end_time=now + timedelta(minutes=15),
                location_name='New York, NY',
                location_lat=Decimal('40.712800'),
                location_lon=Decimal('-74.006000'),
                remarks='Pre-trip inspection',
            ),
            DutyStatusLog(
                driver=self.driver,
                trip=trip,
                status='driving',
                start_time=now + timedelta(minutes=15),
                end_time=now + timedelta(hours=7, minutes=15),
                location_name='Atlanta, GA',
                location_lat=Decimal('33.749000'),
                location_lon=Decimal('-84.388000'),
                remarks='Driving',
            ),
            DutyStatusLog(
                driver=self.driver,
                trip=trip,
                status='off_duty',
                start_time=now + timedelta(hours=7, minutes=15),
                end_time=now + timedelta(hours=17, minutes=15),
                location_name='Charlotte, NC',
                location_lat=Decimal('35.227100'),
                location_lon=Decimal('-80.843100'),
                remarks='10-hour rest',
            ),
        ]
        DutyStatusLog.objects.bulk_create(logs)
        return logs


class TestTripListAPI(TripAPITestCase):
    """Tests for GET /api/trips/."""

    def test_list_trips_returns_200(self):
        self._create_trip()
        self._create_trip(dropoff_location='Nashville, TN')
        response = self.client.get('/api/trips/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 2)

    def test_list_trips_empty(self):
        response = self.client.get('/api/trips/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 0)


class TestTripDetailAPI(TripAPITestCase):
    """Tests for GET /api/trips/{id}/."""

    def test_get_trip_detail_returns_200(self):
        trip = self._create_trip()
        response = self.client.get(f'/api/trips/{trip.id}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['current_location'], 'New York, NY')
        self.assertEqual(response.data['dropoff_location'], 'Atlanta, GA')

    def test_get_nonexistent_trip_returns_404(self):
        response = self.client.get('/api/trips/99999/')
        self.assertEqual(response.status_code, 404)


class TestTripLogsAPI(TripAPITestCase):
    """Tests for GET /api/trips/{id}/logs/."""

    def test_get_trip_logs_returns_entries(self):
        trip = self._create_trip()
        self._create_duty_logs(trip)
        response = self.client.get(f'/api/trips/{trip.id}/logs/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 3)
        # Verify entries are ordered by start_time
        statuses = [entry['status'] for entry in response.data]
        self.assertEqual(statuses, ['on_duty_not_driving', 'driving', 'off_duty'])

    def test_get_trip_logs_empty_trip(self):
        trip = self._create_trip()
        response = self.client.get(f'/api/trips/{trip.id}/logs/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)


class TestTripPDFAPI(TripAPITestCase):
    """Tests for GET /api/trips/{id}/pdf/."""

    def test_pdf_download_returns_pdf(self):
        trip = self._create_trip()
        self._create_duty_logs(trip)
        response = self.client.get(f'/api/trips/{trip.id}/pdf/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('attachment', response['Content-Disposition'])
        # PDF must be non-empty
        self.assertGreater(len(response.content), 0)
        # PDF must start with %PDF header
        self.assertTrue(response.content[:5].startswith(b'%PDF'))

    def test_pdf_download_nonexistent_trip(self):
        response = self.client.get('/api/trips/99999/pdf/')
        self.assertEqual(response.status_code, 404)

    def test_pdf_file_size_reasonable(self):
        """Generated PDF should be between 1KB and 1MB."""
        trip = self._create_trip()
        self._create_duty_logs(trip)
        response = self.client.get(f'/api/trips/{trip.id}/pdf/')
        size = len(response.content)
        self.assertGreater(size, 1024, 'PDF too small (< 1KB)')
        self.assertLess(size, 1024 * 1024, 'PDF too large (> 1MB)')


class TestHOSStatusAPI(TripAPITestCase):
    """Tests for GET /api/hos/status/."""

    def test_hos_status_returns_200(self):
        response = self.client.get('/api/hos/status/')
        self.assertEqual(response.status_code, 200)
        # Must contain key compliance fields
        self.assertIn('driving_hours_remaining', response.data)
        self.assertIn('window_hours_remaining', response.data)
        self.assertIn('can_drive', response.data)
        self.assertIn('violations', response.data)

    def test_hos_status_fresh_driver_can_drive(self):
        response = self.client.get('/api/hos/status/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['can_drive'])
        self.assertEqual(len(response.data['violations']), 0)


class TestHOSValidateAPI(TripAPITestCase):
    """Tests for POST /api/validate/hos/."""

    def test_validate_compliant_entries(self):
        now = timezone.now()
        payload = {
            'entries': [
                {
                    'status': 'off_duty',
                    'start_time': (now - timedelta(hours=10)).isoformat(),
                    'end_time': now.isoformat(),
                },
                {
                    'status': 'driving',
                    'start_time': now.isoformat(),
                    'end_time': (now + timedelta(hours=5)).isoformat(),
                },
            ],
            'historical_days': [],
            'cycle_type': '70_8',
        }
        response = self.client.post(
            '/api/validate/hos/',
            data=payload,
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['can_drive'])

    def test_validate_violation_detected(self):
        now = timezone.now()
        payload = {
            'entries': [
                {
                    'status': 'off_duty',
                    'start_time': (now - timedelta(hours=10)).isoformat(),
                    'end_time': now.isoformat(),
                },
                {
                    'status': 'driving',
                    'start_time': now.isoformat(),
                    'end_time': (now + timedelta(hours=12)).isoformat(),
                },
            ],
            'historical_days': [],
            'cycle_type': '70_8',
        }
        response = self.client.post(
            '/api/validate/hos/',
            data=payload,
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['can_drive'])
        violation_rules = [v['rule'] for v in response.data['violations']]
        self.assertIn('11_hour_driving', violation_rules)


class TestTemplateMappingAPI(TripAPITestCase):
    """Tests for GET/POST /api/templates/mapping/."""

    def test_get_mapping_returns_json(self):
        response = self.client.get('/api/templates/mapping/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('page_size', response.data)
        self.assertIn('graph_grid', response.data)

    def test_post_mapping_updates_and_persists(self):
        # Get current mapping
        original = self.client.get('/api/templates/mapping/').data

        # Modify a value
        modified = dict(original)
        modified['page_size'] = {'width': 612, 'height': 800}

        response = self.client.post(
            '/api/templates/mapping/',
            data=modified,
            format='json',
        )
        self.assertEqual(response.status_code, 200)

        # Verify the change persisted
        response = self.client.get('/api/templates/mapping/')
        self.assertEqual(response.data['page_size']['height'], 800)

        # Restore original
        self.client.post(
            '/api/templates/mapping/',
            data=original,
            format='json',
        )


class TestOpenAPISchema(TripAPITestCase):
    """Tests for OpenAPI schema generation."""

    def test_schema_endpoint_returns_json(self):
        response = self.client.get('/api/schema/', HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 200)
        # Schema must contain openapi version and info
        self.assertIn('openapi', response.data)
        self.assertIn('info', response.data)
        self.assertEqual(response.data['info']['title'], 'HOS Compliance API')
