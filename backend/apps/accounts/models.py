from django.contrib.auth.models import AbstractUser
from django.db import models


class Driver(AbstractUser):
    """Extended user model for truck drivers."""
    license_number = models.CharField(max_length=50, blank=True)
    carrier_name = models.CharField(max_length=200, blank=True)
    carrier_address = models.CharField(max_length=300, blank=True)
    home_terminal_address = models.CharField(max_length=300, blank=True)
    home_terminal_timezone = models.CharField(max_length=50, default='America/Chicago')
    cycle_type = models.CharField(
        max_length=10,
        choices=[('60_7', '60-Hour/7-Day'), ('70_8', '70-Hour/8-Day')],
        default='70_8',
    )
    truck_number = models.CharField(max_length=50, blank=True)
    trailer_number = models.CharField(max_length=50, blank=True)
    co_driver_name = models.CharField(max_length=100, blank=True)

    class Meta:
        db_table = 'drivers'

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.license_number})"
