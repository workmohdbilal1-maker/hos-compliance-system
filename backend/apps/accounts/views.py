import logging
from datetime import timedelta

from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.hos.models import DailyLog
from .models import Driver
from .serializers import DriverSerializer, RegisterSerializer

logger = logging.getLogger(__name__)


class RegisterView(generics.CreateAPIView):
    queryset = Driver.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        driver = serializer.save()
        return Response(DriverSerializer(driver).data, status=201)


class DriverDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = DriverSerializer

    def get_object(self):
        return self.request.user


class DriverHistoryView(APIView):
    """
    GET /api/auth/drivers/{id}/history/?days=8

    Returns historical daily log summaries for the specified driver,
    used to compute the rolling 7/8-day on-duty cycle total.
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request, driver_id):
        try:
            driver = Driver.objects.get(pk=driver_id)
        except Driver.DoesNotExist:
            return Response({'error': 'Driver not found.'}, status=404)

        days = int(request.query_params.get('days', 8))
        days = max(1, min(days, 30))  # Clamp between 1 and 30

        start_date = timezone.now().date() - timedelta(days=days)
        logs = DailyLog.objects.filter(
            driver=driver,
            date__gte=start_date,
        ).order_by('-date')

        data = []
        for log in logs:
            data.append({
                'date': log.date.isoformat(),
                'driving_hours': float(log.driving_hours),
                'on_duty_hours': float(log.on_duty_hours),
                'off_duty_hours': float(log.off_duty_hours),
                'sleeper_hours': float(log.sleeper_hours),
                'total_miles': float(log.total_miles) if log.total_miles else 0,
                'from_location': log.from_location or '',
                'to_location': log.to_location or '',
            })

        return Response({
            'driver_id': driver.id,
            'driver_name': driver.get_full_name() or driver.username,
            'cycle_type': driver.cycle_type,
            'days_requested': days,
            'logs': data,
            'total_on_duty_hours': sum(
                d['driving_hours'] + d['on_duty_hours'] for d in data
            ),
        })


class DriverDataErasureView(APIView):
    """
    DELETE /api/auth/drivers/{id}/data/

    GDPR-style data erasure endpoint. Deletes all personal data
    associated with a driver: trips, duty logs, daily logs, audit logs,
    and then anonymises the driver account.

    Requires authenticated access from the driver themselves.
    """

    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, driver_id):
        try:
            driver = Driver.objects.get(pk=driver_id)
        except Driver.DoesNotExist:
            return Response({'error': 'Driver not found.'}, status=404)

        # Only the driver themselves can request erasure
        if request.user.pk != driver.pk:
            return Response(
                {'error': 'You can only request erasure of your own data.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        from apps.hos.models import AuditLog, DutyStatusLog
        from apps.trips.models import Trip

        # Count records before deletion for the response
        trips_count = Trip.objects.filter(driver=driver).count()
        duty_logs_count = DutyStatusLog.objects.filter(driver=driver).count()
        daily_logs_count = DailyLog.objects.filter(driver=driver).count()
        audit_logs_count = AuditLog.objects.filter(driver=driver).count()

        # Delete all associated data
        Trip.objects.filter(driver=driver).delete()
        DutyStatusLog.objects.filter(driver=driver).delete()
        DailyLog.objects.filter(driver=driver).delete()
        AuditLog.objects.filter(driver=driver).delete()

        # Anonymise the driver account
        driver.first_name = 'Deleted'
        driver.last_name = 'User'
        driver.email = ''
        driver.license_number = ''
        driver.carrier_name = ''
        driver.carrier_address = ''
        driver.home_terminal_address = ''
        driver.truck_number = ''
        driver.trailer_number = ''
        driver.is_active = False
        driver.set_unusable_password()
        driver.save()

        logger.info('GDPR erasure completed for driver %s', driver_id)

        return Response({
            'status': 'Data erasure completed.',
            'records_deleted': {
                'trips': trips_count,
                'duty_logs': duty_logs_count,
                'daily_logs': daily_logs_count,
                'audit_logs': audit_logs_count,
            },
        })
