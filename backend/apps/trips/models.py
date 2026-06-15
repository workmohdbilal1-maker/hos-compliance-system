from django.db import models
from django.conf import settings


class Trip(models.Model):
    """A planned or completed trip with route and HOS schedule."""
    STATUS_CHOICES = [
        ('planning', 'Planning'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    driver = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='trips'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='planning')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Current location (trip start)
    current_location = models.CharField(max_length=200)
    current_lat = models.DecimalField(max_digits=9, decimal_places=6)
    current_lon = models.DecimalField(max_digits=9, decimal_places=6)

    # Pickup
    pickup_location = models.CharField(max_length=200)
    pickup_lat = models.DecimalField(max_digits=9, decimal_places=6)
    pickup_lon = models.DecimalField(max_digits=9, decimal_places=6)

    # Dropoff
    dropoff_location = models.CharField(max_length=200)
    dropoff_lat = models.DecimalField(max_digits=9, decimal_places=6)
    dropoff_lon = models.DecimalField(max_digits=9, decimal_places=6)

    # Cycle info at trip creation
    current_cycle_used = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    # Route data (cached from routing API)
    route_data = models.JSONField(null=True, blank=True)
    total_distance_miles = models.DecimalField(max_digits=8, decimal_places=1, null=True, blank=True)
    estimated_duration_hours = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)

    # Options
    short_haul_exemption = models.BooleanField(default=False)
    adverse_driving = models.BooleanField(default=False)
    sleeper_berth_split_first = models.IntegerField(null=True, blank=True)
    sleeper_berth_split_second = models.IntegerField(null=True, blank=True)

    # HOS summary (computed)
    total_trip_days = models.IntegerField(null=True, blank=True)
    total_driving_hours = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)

    class Meta:
        db_table = 'trips'
        ordering = ['-created_at']

    def __str__(self):
        return f"Trip #{self.id}: {self.current_location} → {self.dropoff_location}"


class TripStop(models.Model):
    """A stop along the route (rest, fuel, pickup, dropoff, etc.)."""
    STOP_TYPE_CHOICES = [
        ('start', 'Start'),
        ('pickup', 'Pickup'),
        ('dropoff', 'Dropoff'),
        ('rest', 'Rest Stop (10hr)'),
        ('fuel', 'Fuel Stop'),
        ('break', '30-Min Break'),
    ]

    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name='stops')
    stop_type = models.CharField(max_length=20, choices=STOP_TYPE_CHOICES)
    location_name = models.CharField(max_length=200)
    lat = models.DecimalField(max_digits=9, decimal_places=6)
    lon = models.DecimalField(max_digits=9, decimal_places=6)
    arrival_time = models.DateTimeField()
    departure_time = models.DateTimeField(null=True, blank=True)
    sequence = models.IntegerField()
    duration_minutes = models.IntegerField(default=0)

    class Meta:
        db_table = 'trip_stops'
        ordering = ['sequence']

    def __str__(self):
        return f"{self.stop_type}: {self.location_name}"
