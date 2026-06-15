from rest_framework import serializers

from apps.hos.models import DutyStatusLog


class DutyStatusLogSerializer(serializers.ModelSerializer):
    """Serializer for individual duty status log entries."""

    driver = serializers.PrimaryKeyRelatedField(read_only=True)
    duration_hours = serializers.FloatField(read_only=True)

    class Meta:
        model = DutyStatusLog
        fields = [
            'id',
            'driver',
            'status',
            'start_time',
            'end_time',
            'location_name',
            'location_lat',
            'location_lon',
            'odometer',
            'remarks',
            'is_personal_conveyance',
            'is_yard_move',
            'trip',
            'duration_hours',
        ]
        read_only_fields = ['id', 'driver', 'duration_hours']


class HOSViolationSerializer(serializers.Serializer):
    """Serializer for an individual HOS violation."""

    rule = serializers.CharField()
    description = serializers.CharField()
    violation_time = serializers.DateTimeField(allow_null=True)
    severity = serializers.CharField()


class HOSStatusSerializer(serializers.Serializer):
    """
    Serializer for the HOSStatus dataclass returned by HOSCalculator.

    Maps all fields from engine.HOSStatus so the dataclass can be
    serialized directly to JSON for the REST API response.
    """

    driving_hours_used = serializers.FloatField()
    driving_hours_remaining = serializers.FloatField()
    window_hours_used = serializers.FloatField()
    window_hours_remaining = serializers.FloatField()
    break_hours_driving_since_last = serializers.FloatField()
    break_required = serializers.BooleanField()
    cycle_hours_used = serializers.FloatField()
    cycle_hours_remaining = serializers.FloatField()
    cycle_type = serializers.SerializerMethodField()
    can_drive = serializers.BooleanField()
    violations = HOSViolationSerializer(many=True)
    current_duty_status = serializers.SerializerMethodField()
    window_start = serializers.DateTimeField(allow_null=True)
    window_end = serializers.DateTimeField(allow_null=True)
    explanations = serializers.ListField(child=serializers.CharField())

    def get_cycle_type(self, obj):
        val = getattr(obj, 'cycle_type', None)
        return val.value if hasattr(val, 'value') else str(val)

    def get_current_duty_status(self, obj):
        val = getattr(obj, 'current_duty_status', None)
        if val is None:
            return None
        return val.value if hasattr(val, 'value') else str(val)


class DutyStatusEntryInputSerializer(serializers.Serializer):
    """Input serializer for a single duty-status entry used in validation."""

    status = serializers.ChoiceField(
        choices=['off_duty', 'sleeper_berth', 'driving', 'on_duty_not_driving']
    )
    start_time = serializers.DateTimeField()
    end_time = serializers.DateTimeField(required=False, allow_null=True)
    location = serializers.CharField(required=False, allow_blank=True, default='')
    lat = serializers.FloatField(required=False, allow_null=True, default=None)
    lon = serializers.FloatField(required=False, allow_null=True, default=None)
    odometer = serializers.FloatField(required=False, allow_null=True, default=None)
    remarks = serializers.CharField(required=False, allow_blank=True, default='')


class DriverDayInputSerializer(serializers.Serializer):
    """Input serializer for a single historical DriverDay used in validation."""

    day_date = serializers.DateField()
    on_duty_hours = serializers.FloatField(default=0.0)
    driving_hours = serializers.FloatField(default=0.0)
    off_duty_hours = serializers.FloatField(default=0.0)
    sleeper_hours = serializers.FloatField(default=0.0)


class HOSValidationSerializer(serializers.Serializer):
    """
    Input serializer for the ValidateHOS endpoint.

    Accepts arbitrary duty-status entries and historical day summaries
    so the caller can validate any set of logs against HOS rules without
    persisting data.
    """

    entries = DutyStatusEntryInputSerializer(many=True)
    historical_days = DriverDayInputSerializer(many=True, required=False, default=[])
    cycle_type = serializers.ChoiceField(
        choices=['60_7', '70_8'], default='70_8', required=False
    )
    adverse_driving = serializers.BooleanField(default=False, required=False)
    short_haul_exempt = serializers.BooleanField(default=False, required=False)
