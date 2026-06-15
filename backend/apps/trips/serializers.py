from rest_framework import serializers

from apps.hos.serializers import DutyStatusLogSerializer
from apps.trips.models import Trip, TripStop


class TripStopSerializer(serializers.ModelSerializer):
    """Serializer for stops along a trip route."""

    class Meta:
        model = TripStop
        fields = [
            'id',
            'trip',
            'stop_type',
            'location_name',
            'lat',
            'lon',
            'arrival_time',
            'departure_time',
            'sequence',
            'duration_minutes',
        ]
        read_only_fields = ['id', 'trip']


class DutyStatusEntrySerializer(serializers.Serializer):
    """Serializer for individual duty status entries within daily summaries."""
    status = serializers.CharField()
    start_time = serializers.DateTimeField()
    end_time = serializers.DateTimeField(allow_null=True)
    location = serializers.CharField(allow_blank=True, default='')
    remarks = serializers.CharField(allow_blank=True, default='')


class DailySummarySerializer(serializers.Serializer):
    """Serializer for per-day duty log summaries."""
    date = serializers.DateField()
    entries = DutyStatusEntrySerializer(many=True)
    driving_hours = serializers.FloatField()
    on_duty_hours = serializers.FloatField()
    off_duty_hours = serializers.FloatField()
    sleeper_hours = serializers.FloatField()


class TripSerializer(serializers.ModelSerializer):
    """
    Read serializer for Trip with nested stops and computed read-only fields.
    Used for list/detail responses.
    """

    stops = TripStopSerializer(many=True, read_only=True)
    duty_logs = DutyStatusLogSerializer(many=True, read_only=True)
    daily_summaries = serializers.SerializerMethodField()
    driver = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Trip
        fields = [
            'id',
            'driver',
            'status',
            'created_at',
            'updated_at',
            # Locations
            'current_location',
            'current_lat',
            'current_lon',
            'pickup_location',
            'pickup_lat',
            'pickup_lon',
            'dropoff_location',
            'dropoff_lat',
            'dropoff_lon',
            # Cycle
            'current_cycle_used',
            # Route data
            'route_data',
            'total_distance_miles',
            'estimated_duration_hours',
            # Options
            'short_haul_exemption',
            'adverse_driving',
            'sleeper_berth_split_first',
            'sleeper_berth_split_second',
            # HOS summary
            'total_trip_days',
            'total_driving_hours',
            # Nested
            'stops',
            'duty_logs',
            'daily_summaries',
        ]
        read_only_fields = [
            'id',
            'driver',
            'created_at',
            'updated_at',
            'route_data',
            'total_distance_miles',
            'estimated_duration_hours',
            'total_trip_days',
            'total_driving_hours',
        ]

    def get_daily_summaries(self, obj):
        """Build per-day duty log summaries from the trip's duty logs."""
        from collections import defaultdict

        logs = obj.duty_logs.order_by('start_time')
        if not logs.exists():
            return []

        days_map = defaultdict(list)
        for log in logs:
            day_key = log.start_time.date()
            days_map[day_key].append({
                'status': log.status,
                'start_time': log.start_time,
                'end_time': log.end_time,
                'location': log.location_name or '',
                'remarks': log.remarks or '',
            })

        summaries = []
        for day_date in sorted(days_map.keys()):
            entries = days_map[day_date]
            driving = on_duty = off_duty = sleeper = 0.0

            for e in entries:
                if e['end_time'] and e['start_time']:
                    hours = (e['end_time'] - e['start_time']).total_seconds() / 3600
                else:
                    hours = 0.0
                if e['status'] == 'driving':
                    driving += hours
                elif e['status'] == 'on_duty_not_driving':
                    on_duty += hours
                elif e['status'] == 'off_duty':
                    off_duty += hours
                elif e['status'] == 'sleeper_berth':
                    sleeper += hours

            summaries.append({
                'date': str(day_date),
                'entries': entries,
                'driving_hours': round(driving, 1),
                'on_duty_hours': round(on_duty, 1),
                'off_duty_hours': round(off_duty, 1),
                'sleeper_hours': round(sleeper, 1),
            })

        return summaries


class LocationSerializer(serializers.Serializer):
    """Accepts a location as lat/lng with an optional name."""

    lat = serializers.FloatField()
    lng = serializers.FloatField()
    name = serializers.CharField(required=False, default='')


class TripOptionsSerializer(serializers.Serializer):
    """Optional trip planning configuration."""

    short_haul_exemption = serializers.BooleanField(default=False, required=False)
    adverse_driving = serializers.BooleanField(default=False, required=False)
    sleeper_berth_split_first = serializers.IntegerField(
        required=False, allow_null=True, default=None
    )
    sleeper_berth_split_second = serializers.IntegerField(
        required=False, allow_null=True, default=None
    )


class TripCreateSerializer(serializers.Serializer):
    """
    Input serializer for creating a new trip via POST.

    Accepts current, pickup, and dropoff locations as lat/lng dicts,
    plus the driver's current cycle hours used and optional planning options.
    """

    current_location = LocationSerializer()
    pickup_location = LocationSerializer()
    dropoff_location = LocationSerializer()
    cycle_hours_used = serializers.FloatField(default=0.0, required=False)
    options = TripOptionsSerializer(required=False, default={})
