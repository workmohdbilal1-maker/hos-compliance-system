from django.db import models
from django.conf import settings


class DutyStatusLog(models.Model):
    """Individual duty status entry - the atomic unit of HOS tracking."""
    STATUS_CHOICES = [
        ('off_duty', 'Off Duty'),
        ('sleeper_berth', 'Sleeper Berth'),
        ('driving', 'Driving'),
        ('on_duty_not_driving', 'On Duty (Not Driving)'),
    ]

    driver = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='duty_logs'
    )
    status = models.CharField(max_length=30, choices=STATUS_CHOICES)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)
    location_name = models.CharField(max_length=200, blank=True)
    location_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    location_lon = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    odometer = models.DecimalField(max_digits=9, decimal_places=1, null=True, blank=True)
    remarks = models.TextField(blank=True)
    is_personal_conveyance = models.BooleanField(default=False)
    is_yard_move = models.BooleanField(default=False)

    # Link to trip if generated from trip planning
    trip = models.ForeignKey(
        'trips.Trip', on_delete=models.SET_NULL, null=True, blank=True, related_name='duty_logs'
    )

    class Meta:
        db_table = 'duty_status_logs'
        ordering = ['start_time']
        indexes = [
            models.Index(fields=['driver', 'start_time']),
            models.Index(fields=['driver', 'status']),
        ]

    def __str__(self):
        return f"{self.driver} - {self.status} @ {self.start_time}"

    @property
    def duration_hours(self):
        if self.end_time and self.start_time:
            return (self.end_time - self.start_time).total_seconds() / 3600
        return 0


class DailyLog(models.Model):
    """Aggregated daily summary for a driver - one per day."""
    driver = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='daily_logs'
    )
    date = models.DateField()
    total_miles = models.DecimalField(max_digits=7, decimal_places=1, default=0)
    total_mileage = models.DecimalField(max_digits=9, decimal_places=1, default=0)
    off_duty_hours = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    sleeper_hours = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    driving_hours = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    on_duty_hours = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    shipping_doc = models.CharField(max_length=200, blank=True)
    shipper_commodity = models.CharField(max_length=200, blank=True)
    from_location = models.CharField(max_length=200, blank=True)
    to_location = models.CharField(max_length=200, blank=True)

    class Meta:
        db_table = 'daily_logs'
        unique_together = ['driver', 'date']
        ordering = ['-date']

    def __str__(self):
        return f"{self.driver} - {self.date}"

    @property
    def total_hours(self):
        return float(self.off_duty_hours + self.sleeper_hours +
                     self.driving_hours + self.on_duty_hours)

    @property
    def on_duty_total(self):
        """Total on-duty time (driving + on-duty not driving) for cycle calculations."""
        return float(self.driving_hours + self.on_duty_hours)


class AuditLog(models.Model):
    """
    Immutable audit trail for HOS decisions, plan generation, and PDF output.

    Records who requested the action, what inputs were provided, what rules
    were triggered, and the outcome. Used for regulatory traceability and appeals.
    """
    ACTION_CHOICES = [
        ('trip_plan', 'Trip Plan Generated'),
        ('pdf_generated', 'RODS PDF Generated'),
        ('hos_validation', 'HOS Validation Run'),
        ('hos_status', 'HOS Status Checked'),
        ('template_mapping_update', 'Template Mapping Updated'),
    ]

    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    driver = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='audit_logs',
    )
    trip = models.ForeignKey(
        'trips.Trip', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='audit_logs',
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    inputs = models.JSONField(default=dict, blank=True)
    outputs = models.JSONField(default=dict, blank=True)
    rules_triggered = models.JSONField(default=list, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        db_table = 'audit_logs'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['driver', 'timestamp']),
            models.Index(fields=['action', 'timestamp']),
        ]

    def __str__(self):
        return f"[{self.timestamp}] {self.action} - Driver: {self.driver_id}"
