import json
import logging

from django.conf import settings
from django.http import HttpResponse
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.trips.models import Trip

logger = logging.getLogger(__name__)


class TripPDFView(APIView):
    """
    GET /api/trips/<trip_id>/pdf/

    Generates and returns a PDF document for the specified trip.

    Uses the pdf_gen.generator module (to be implemented later).
    Returns a placeholder PDF if the generator is not yet available.
    """

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'pdf_download'

    def get(self, request, trip_id):
        try:
            trip = Trip.objects.get(pk=trip_id)
        except Trip.DoesNotExist:
            return Response(
                {'error': 'Trip not found.'},
                status=404,
            )

        # Attempt to use the real PDF generator module.
        # Falls back to a placeholder if the module is not yet implemented.
        try:
            from apps.pdf_gen.generator import generate_trip_pdf

            pdf_bytes = generate_trip_pdf(trip)
        except ImportError:
            logger.info(
                'PDF generator module not yet implemented. '
                'Returning placeholder for trip %s.',
                trip_id,
            )
            pdf_bytes = self._generate_placeholder_pdf(trip)
        except Exception as exc:
            logger.exception('PDF generation failed for trip %s: %s', trip_id, exc)
            return Response(
                {'error': f'PDF generation failed: {str(exc)}'},
                status=500,
            )

        # Audit log
        try:
            from apps.hos.models import AuditLog
            AuditLog.objects.create(
                action='pdf_generated',
                driver=trip.driver,
                trip=trip,
                outputs={'pdf_size_bytes': len(pdf_bytes)},
                ip_address=request.META.get('REMOTE_ADDR'),
            )
        except Exception:
            pass  # Audit logging should never block the response

        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = (
            f'attachment; filename="trip_{trip.id}_log.pdf"'
        )
        return response

    @staticmethod
    def _generate_placeholder_pdf(trip):
        """
        Generate a minimal placeholder PDF using reportlab.
        Returns bytes suitable for an HTTP response.
        """
        try:
            from io import BytesIO

            from reportlab.lib.pagesizes import letter
            from reportlab.pdfgen import canvas

            buffer = BytesIO()
            c = canvas.Canvas(buffer, pagesize=letter)
            width, height = letter

            c.setFont('Helvetica-Bold', 16)
            c.drawString(72, height - 72, f'Trip #{trip.id} - Driver Log')

            c.setFont('Helvetica', 11)
            y = height - 110
            lines = [
                f'Driver: {trip.driver.get_full_name() or trip.driver.username}',
                f'From: {trip.current_location}',
                f'Pickup: {trip.pickup_location}',
                f'Dropoff: {trip.dropoff_location}',
                f'Status: {trip.status}',
                f'Created: {trip.created_at.strftime("%Y-%m-%d %H:%M") if trip.created_at else "N/A"}',
                f'Total Distance: {trip.total_distance_miles or "N/A"} miles',
                f'Estimated Duration: {trip.estimated_duration_hours or "N/A"} hours',
                f'Total Trip Days: {trip.total_trip_days or "N/A"}',
                f'Total Driving Hours: {trip.total_driving_hours or "N/A"}',
            ]

            for line in lines:
                c.drawString(72, y, line)
                y -= 20

            y -= 20
            c.setFont('Helvetica-Oblique', 10)
            c.drawString(
                72, y,
                'This is a placeholder PDF. Full ELD-style logs will be generated '
                'once the pdf_gen.generator module is implemented.',
            )

            c.showPage()
            c.save()
            buffer.seek(0)
            return buffer.read()

        except ImportError:
            # reportlab not installed -- return a minimal PDF stub
            return b'%PDF-1.4 placeholder - reportlab not available'


class TemplateMappingView(APIView):
    """
    GET  /api/templates/mapping/ -- Return the current ELD template mapping JSON.
    POST /api/templates/mapping/ -- Update the mapping and persist to disk.

    Allows runtime reconfiguration of PDF field coordinates without code changes.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        mapping_path = getattr(settings, 'ELD_MAPPING_PATH', None)
        if not mapping_path or not mapping_path.exists():
            return Response({'error': 'Mapping file not found.'}, status=404)
        try:
            with open(mapping_path, 'r') as f:
                mapping = json.load(f)
            return Response(mapping)
        except (json.JSONDecodeError, IOError) as exc:
            return Response({'error': str(exc)}, status=500)

    def post(self, request):
        mapping_path = getattr(settings, 'ELD_MAPPING_PATH', None)
        if not mapping_path:
            return Response({'error': 'ELD_MAPPING_PATH not configured.'}, status=500)

        mapping_data = request.data
        if not isinstance(mapping_data, dict):
            return Response({'error': 'Request body must be a JSON object.'}, status=400)

        try:
            with open(mapping_path, 'w') as f:
                json.dump(mapping_data, f, indent=2)
            return Response({'status': 'Mapping updated successfully.'})
        except IOError as exc:
            return Response({'error': str(exc)}, status=500)
