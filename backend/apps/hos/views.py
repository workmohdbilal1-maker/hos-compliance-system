from datetime import datetime, timedelta

from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.hos.engine import (
    CycleType,
    DriverDay,
    DutyStatus,
    DutyStatusEntry,
    HOSCalculator,
)
from apps.hos.models import DailyLog, DutyStatusLog
from apps.hos.serializers import (
    DutyStatusLogSerializer,
    HOSStatusSerializer,
    HOSValidationSerializer,
)


class HOSStatusView(APIView):
    """
    GET /api/hos/status/

    Computes the current HOS compliance status for the authenticated driver.
    Fetches recent DutyStatusLog entries and DailyLog history, feeds them
    into HOSCalculator, and returns a complete HOSStatus response.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        driver = request.user
        now = timezone.now()

        # Determine cycle type from driver profile
        cycle_type = CycleType(driver.cycle_type)
        calculator = HOSCalculator(cycle_type=cycle_type)

        # Fetch duty status logs from the current duty window.
        # We look back 14 days to ensure we capture the last qualifying rest
        # and any relevant entries.
        window_start = now - timedelta(days=14)
        logs = DutyStatusLog.objects.filter(
            driver=driver,
            start_time__gte=window_start,
        ).order_by('start_time')

        # Convert ORM records to engine dataclass entries
        entries = []
        for log in logs:
            entries.append(
                DutyStatusEntry(
                    status=DutyStatus(log.status),
                    start_time=log.start_time,
                    end_time=log.end_time,
                    location=log.location_name or '',
                    lat=float(log.location_lat) if log.location_lat else None,
                    lon=float(log.location_lon) if log.location_lon else None,
                    odometer=float(log.odometer) if log.odometer else None,
                    remarks=log.remarks or '',
                )
            )

        # Fetch historical daily log summaries for cycle calculation.
        # Need up to 8 days (for 70/8 cycle) of history.
        cycle_days = 8 if cycle_type == CycleType.SEVENTY_EIGHT else 7
        history_start = now.date() - timedelta(days=cycle_days)
        daily_logs = DailyLog.objects.filter(
            driver=driver,
            date__gte=history_start,
            date__lt=now.date(),  # Exclude today (computed from entries)
        ).order_by('-date')

        historical_days = []
        for dl in daily_logs:
            historical_days.append(
                DriverDay(
                    day_date=dl.date,
                    on_duty_hours=float(dl.driving_hours + dl.on_duty_hours),
                    driving_hours=float(dl.driving_hours),
                    off_duty_hours=float(dl.off_duty_hours),
                    sleeper_hours=float(dl.sleeper_hours),
                )
            )

        # Run the HOS calculator
        hos_status = calculator.calculate_hos_status(
            entries=entries,
            historical_days=historical_days,
            current_time=now,
            adverse_driving=False,
            short_haul_exempt=False,
        )

        serializer = HOSStatusSerializer(hos_status)
        return Response(serializer.data)


class ValidateHOSView(APIView):
    """
    POST /api/validate/hos/

    Accepts arbitrary duty-status entries and historical day summaries,
    runs the HOS calculator, and returns the validation result.

    This endpoint does not persist anything; it is purely computational.
    Useful for trip-planning "what-if" scenarios.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = HOSValidationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Build engine objects from validated input
        entries = []
        for entry_data in data['entries']:
            entries.append(
                DutyStatusEntry(
                    status=DutyStatus(entry_data['status']),
                    start_time=entry_data['start_time'],
                    end_time=entry_data.get('end_time'),
                    location=entry_data.get('location', ''),
                    lat=entry_data.get('lat'),
                    lon=entry_data.get('lon'),
                    odometer=entry_data.get('odometer'),
                    remarks=entry_data.get('remarks', ''),
                )
            )

        historical_days = []
        for day_data in data.get('historical_days', []):
            historical_days.append(
                DriverDay(
                    day_date=day_data['day_date'],
                    on_duty_hours=day_data.get('on_duty_hours', 0.0),
                    driving_hours=day_data.get('driving_hours', 0.0),
                    off_duty_hours=day_data.get('off_duty_hours', 0.0),
                    sleeper_hours=day_data.get('sleeper_hours', 0.0),
                )
            )

        cycle_type = CycleType(data.get('cycle_type', '70_8'))
        calculator = HOSCalculator(cycle_type=cycle_type)

        now = timezone.now()
        hos_status = calculator.calculate_hos_status(
            entries=entries,
            historical_days=historical_days,
            current_time=now,
            adverse_driving=data.get('adverse_driving', False),
            short_haul_exempt=data.get('short_haul_exempt', False),
        )

        result_serializer = HOSStatusSerializer(hos_status)
        return Response(result_serializer.data)


class DutyStatusLogListView(generics.ListCreateAPIView):
    """
    GET  /api/hos/logs/  -- List duty status logs for the authenticated driver.
    POST /api/hos/logs/  -- Create a new duty status log entry.

    Results are ordered by start_time descending (most recent first).
    Supports filtering via query parameters:
      - ?trip=<id>   filter by trip
      - ?status=<status>   filter by duty status
      - ?from=<iso-datetime>   logs starting after this time
      - ?to=<iso-datetime>   logs starting before this time
    """

    serializer_class = DutyStatusLogSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        qs = DutyStatusLog.objects.filter(driver=self.request.user)

        # Optional filters
        trip_id = self.request.query_params.get('trip')
        if trip_id:
            qs = qs.filter(trip_id=trip_id)

        duty_status = self.request.query_params.get('status')
        if duty_status:
            qs = qs.filter(status=duty_status)

        from_time = self.request.query_params.get('from')
        if from_time:
            qs = qs.filter(start_time__gte=from_time)

        to_time = self.request.query_params.get('to')
        if to_time:
            qs = qs.filter(start_time__lte=to_time)

        return qs.order_by('-start_time')

    def perform_create(self, serializer):
        serializer.save(driver=self.request.user)
