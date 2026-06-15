import logging

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.hos.models import DutyStatusLog
from apps.hos.serializers import DutyStatusLogSerializer
from apps.trips.models import Trip
from apps.trips.serializers import TripCreateSerializer, TripSerializer
from apps.trips.services import RouteService, TripPlannerService

logger = logging.getLogger(__name__)


def _get_or_create_demo_driver():
    """Get or create a demo driver for unauthenticated requests."""
    from apps.accounts.models import Driver
    driver, created = Driver.objects.get_or_create(
        username='demo_driver',
        defaults={
            'first_name': 'Demo',
            'last_name': 'Driver',
            'carrier_name': 'Spotter Transport LLC',
            'carrier_address': '123 Main St, Chicago, IL 60601',
            'home_terminal_address': '123 Main St, Chicago, IL 60601',
            'cycle_type': '70_8',
            'truck_number': 'TRK-1234',
        }
    )
    if created:
        driver.set_password('demo123')
        driver.save()
    return driver


class TripViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Trip CRUD operations.

    list:   GET    /api/trips/
    create: POST   /api/trips/       (uses TripPlannerService)
    read:   GET    /api/trips/{id}/
    update: PUT    /api/trips/{id}/
    delete: DELETE /api/trips/{id}/

    Extra actions:
      - logs: GET /api/trips/{id}/logs/   (duty logs for this trip)
      - pdf:  GET /api/trips/{id}/pdf/    (download PDF)
    """

    serializer_class = TripSerializer
    permission_classes = [AllowAny]

    def _get_driver(self):
        """Get the authenticated user or fall back to the demo driver."""
        if self.request.user and self.request.user.is_authenticated:
            return self.request.user
        return _get_or_create_demo_driver()

    def get_queryset(self):
        driver = self._get_driver()
        return Trip.objects.filter(
            driver=driver
        ).prefetch_related('stops', 'duty_logs')

    def get_serializer_class(self):
        if self.action == 'create':
            return TripCreateSerializer
        return TripSerializer

    def create(self, request, *args, **kwargs):
        """
        Create a new trip using the TripPlannerService.

        Accepts current_location, pickup_location, dropoff_location as
        {lat, lng, name} dicts, plus cycle_hours_used and options.
        """
        serializer = TripCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        planner = TripPlannerService()
        driver = self._get_driver()
        try:
            trip = planner.plan_trip(
                driver=driver,
                current_location=data['current_location'],
                pickup_location=data['pickup_location'],
                dropoff_location=data['dropoff_location'],
                cycle_hours_used=data.get('cycle_hours_used', 0.0),
                options=data.get('options', {}),
            )
        except Exception as exc:
            logger.exception('Trip planning failed: %s', exc)
            return Response(
                {'error': f'Trip planning failed: {str(exc)}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Audit log
        try:
            from apps.hos.models import AuditLog
            AuditLog.objects.create(
                action='trip_plan',
                driver=driver,
                trip=trip,
                inputs={
                    'current_location': str(data['current_location']),
                    'pickup_location': str(data['pickup_location']),
                    'dropoff_location': str(data['dropoff_location']),
                    'cycle_hours_used': float(data.get('cycle_hours_used', 0)),
                },
                outputs={
                    'total_distance_miles': float(trip.total_distance_miles or 0),
                    'total_trip_days': trip.total_trip_days,
                    'total_driving_hours': float(trip.total_driving_hours or 0),
                },
                ip_address=request.META.get('REMOTE_ADDR'),
            )
        except Exception:
            pass  # Audit logging should never block the response

        # Re-fetch with prefetched relations for the response
        trip = Trip.objects.prefetch_related('stops', 'duty_logs').get(pk=trip.pk)
        response_serializer = TripSerializer(trip)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'], url_path='logs')
    def logs(self, request, pk=None):
        """
        GET /api/trips/{id}/logs/

        Returns all duty status log entries associated with this trip.
        """
        trip = self.get_object()
        driver = self._get_driver()
        duty_logs = DutyStatusLog.objects.filter(
            trip=trip,
            driver=driver,
        ).order_by('start_time')

        serializer = DutyStatusLogSerializer(duty_logs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'], url_path='pdf')
    def pdf(self, request, pk=None):
        """
        GET /api/trips/{id}/pdf/

        Generates and returns a PDF document for the trip.
        Delegates to the pdf_gen module.
        """
        trip = self.get_object()

        # Import here to avoid circular imports; the generator module
        # will be implemented later.
        try:
            from apps.pdf_gen.generator import generate_trip_pdf

            pdf_bytes = generate_trip_pdf(trip)
            from django.http import HttpResponse

            response = HttpResponse(pdf_bytes, content_type='application/pdf')
            response['Content-Disposition'] = (
                f'attachment; filename="trip_{trip.id}_log.pdf"'
            )
            return response
        except ImportError:
            # Generator not yet implemented -- return placeholder
            from django.http import HttpResponse

            response = HttpResponse(
                b'%PDF-1.4 placeholder', content_type='application/pdf'
            )
            response['Content-Disposition'] = (
                f'attachment; filename="trip_{trip.id}_log.pdf"'
            )
            return response


class RouteView(APIView):
    """
    GET /api/maps/route/?coordinates=lon1,lat1|lon2,lat2|...

    Proxy endpoint for the OpenRouteService directions API.
    Used by the frontend for map route preview without exposing the
    ORS API key to the client.
    """

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'route_api'

    def get(self, request):
        coordinates_param = request.query_params.get('coordinates', '')
        if not coordinates_param:
            return Response(
                {'error': 'Missing "coordinates" query parameter. '
                          'Format: lon1,lat1|lon2,lat2|...'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            coordinates = []
            for pair in coordinates_param.split('|'):
                parts = pair.strip().split(',')
                if len(parts) != 2:
                    raise ValueError(f'Invalid coordinate pair: {pair}')
                lon, lat = float(parts[0]), float(parts[1])
                coordinates.append([lon, lat])
        except (ValueError, IndexError) as exc:
            return Response(
                {'error': f'Invalid coordinates format: {exc}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(coordinates) < 2:
            return Response(
                {'error': 'At least two coordinate pairs are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        route_service = RouteService()
        try:
            data = route_service.get_route(coordinates)
        except ValueError as exc:
            return Response(
                {'error': str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception as exc:
            logger.exception('Route API call failed: %s', exc)
            return Response(
                {'error': f'Route service error: {str(exc)}'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(data)


class GeocodeView(APIView):
    """
    GET /api/maps/geocode/?q=Philadelphia,+PA

    Proxy endpoint for the OpenRouteService geocode API.
    Returns matching locations with coordinates so the frontend can
    auto-fill lat/lng when the user types a location name.
    """

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'route_api'

    def get(self, request):
        query = request.query_params.get('q', '').strip()
        if not query or len(query) < 2:
            return Response(
                {'error': 'Query parameter "q" is required (min 2 chars).'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        route_service = RouteService()
        try:
            data = route_service.geocode(query)
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            logger.exception('Geocode API call failed: %s', exc)
            return Response(
                {'error': f'Geocode service error: {str(exc)}'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # Simplify the response for the frontend
        results = []
        for feature in data.get('features', []):
            props = feature.get('properties', {})
            coords = feature.get('geometry', {}).get('coordinates', [])
            if len(coords) >= 2:
                results.append({
                    'name': props.get('label', ''),
                    'lat': coords[1],
                    'lng': coords[0],
                    'country': props.get('country', ''),
                    'region': props.get('region', ''),
                })

        return Response({'results': results})
