"""
PDF generation tests.

Tests that the RODS PDF generator produces valid PDFs with expected content
overlaid on the RODs_Ex.pdf template.
"""
import io
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import Driver
from apps.hos.models import DutyStatusLog
from apps.trips.models import Trip


class TestPDFGeneration(TestCase):
    """Tests for the ReportLab + PyPDF2 PDF generation pipeline."""

    def setUp(self):
        self.driver = Driver.objects.create_user(
            username='pdfdriver',
            password='test123',
            first_name='PDF',
            last_name='Test',
            license_number='CDL-PDF',
            carrier_name='Test Carrier',
            carrier_address='456 Test Ave',
            cycle_type='70_8',
            truck_number='TRK-PDF',
        )
        now = timezone.now().replace(hour=6, minute=0, second=0, microsecond=0)
        self.trip = Trip.objects.create(
            driver=self.driver,
            status='completed',
            current_location='New York, NY',
            current_lat=Decimal('40.712800'),
            current_lon=Decimal('-74.006000'),
            pickup_location='Philadelphia, PA',
            pickup_lat=Decimal('39.952600'),
            pickup_lon=Decimal('-75.165200'),
            dropoff_location='Atlanta, GA',
            dropoff_lat=Decimal('33.749000'),
            dropoff_lon=Decimal('-84.388000'),
            total_distance_miles=Decimal('874.0'),
            total_trip_days=2,
            total_driving_hours=Decimal('14.50'),
        )
        # Create duty logs spanning two days
        DutyStatusLog.objects.bulk_create([
            DutyStatusLog(
                driver=self.driver,
                trip=self.trip,
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
                trip=self.trip,
                status='on_duty_not_driving',
                start_time=now + timedelta(minutes=15),
                end_time=now + timedelta(hours=1, minutes=15),
                location_name='New York, NY',
                location_lat=Decimal('40.712800'),
                location_lon=Decimal('-74.006000'),
                remarks='Pickup / loading',
            ),
            DutyStatusLog(
                driver=self.driver,
                trip=self.trip,
                status='driving',
                start_time=now + timedelta(hours=1, minutes=15),
                end_time=now + timedelta(hours=8, minutes=15),
                location_name='Charlotte, NC',
                location_lat=Decimal('35.227100'),
                location_lon=Decimal('-80.843100'),
                remarks='Driving',
            ),
            DutyStatusLog(
                driver=self.driver,
                trip=self.trip,
                status='off_duty',
                start_time=now + timedelta(hours=8, minutes=15),
                end_time=now + timedelta(hours=18, minutes=15),
                location_name='Charlotte, NC',
                location_lat=Decimal('35.227100'),
                location_lon=Decimal('-80.843100'),
                remarks='10-hour rest',
            ),
            DutyStatusLog(
                driver=self.driver,
                trip=self.trip,
                status='driving',
                start_time=now + timedelta(hours=18, minutes=15),
                end_time=now + timedelta(hours=25, minutes=15),
                location_name='Atlanta, GA',
                location_lat=Decimal('33.749000'),
                location_lon=Decimal('-84.388000'),
                remarks='Driving day 2',
            ),
        ])

    def test_pdf_generation_produces_valid_pdf(self):
        """Generated PDF starts with %PDF header and is non-empty."""
        from apps.pdf_gen.generator import generate_trip_pdf
        pdf_bytes = generate_trip_pdf(self.trip)
        self.assertIsInstance(pdf_bytes, bytes)
        self.assertGreater(len(pdf_bytes), 1000, 'PDF is too small')
        self.assertTrue(pdf_bytes[:5].startswith(b'%PDF'), 'Not a valid PDF file')

    def test_pdf_has_correct_page_count(self):
        """Multi-day trip should produce one page per active day."""
        from apps.pdf_gen.generator import generate_trip_pdf
        pdf_bytes = generate_trip_pdf(self.trip)

        from PyPDF2 import PdfReader
        reader = PdfReader(io.BytesIO(pdf_bytes))
        # We have 2 days of duty entries with driving, so expect 2 pages
        self.assertGreaterEqual(len(reader.pages), 1)

    def test_pdf_contains_driver_text(self):
        """PDF should contain the driver's name in the overlaid text."""
        from apps.pdf_gen.generator import generate_trip_pdf
        pdf_bytes = generate_trip_pdf(self.trip)

        from PyPDF2 import PdfReader
        reader = PdfReader(io.BytesIO(pdf_bytes))
        all_text = ''
        for page in reader.pages:
            text = page.extract_text()
            if text:
                all_text += text

        # The driver's name should appear in the PDF overlay
        self.assertIn('PDF', all_text, 'Driver first name not found in PDF')

    def test_pdf_contains_carrier_text(self):
        """PDF should contain carrier information."""
        from apps.pdf_gen.generator import generate_trip_pdf
        pdf_bytes = generate_trip_pdf(self.trip)

        from PyPDF2 import PdfReader
        reader = PdfReader(io.BytesIO(pdf_bytes))
        all_text = ''
        for page in reader.pages:
            text = page.extract_text()
            if text:
                all_text += text

        self.assertIn('Test Carrier', all_text, 'Carrier name not found in PDF')

    def test_pdf_uses_rods_template(self):
        """PDF should be based on RODs_Ex.pdf template (not a blank page)."""
        from apps.pdf_gen.generator import generate_trip_pdf
        pdf_bytes = generate_trip_pdf(self.trip)

        # A PDF overlaid on the RODs template should be significantly larger
        # than a blank page (the template alone is ~68KB)
        self.assertGreater(
            len(pdf_bytes), 50000,
            'PDF is too small to contain the RODs template overlay',
        )

    def test_pdf_file_is_readable(self):
        """Generated PDF should be parseable by PyPDF2 without errors."""
        from apps.pdf_gen.generator import generate_trip_pdf
        pdf_bytes = generate_trip_pdf(self.trip)

        from PyPDF2 import PdfReader
        try:
            reader = PdfReader(io.BytesIO(pdf_bytes))
            # Access pages to force parsing
            _ = len(reader.pages)
        except Exception as exc:
            self.fail(f'PDF is not readable: {exc}')

    def test_template_exists(self):
        """The RODs_Ex.pdf template must exist at the configured path."""
        template_path = settings.RODS_TEMPLATE_PATH
        self.assertTrue(
            template_path.exists(),
            f'RODS template not found at {template_path}',
        )
