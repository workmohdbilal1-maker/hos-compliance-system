from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Driver


@admin.register(Driver)
class DriverAdmin(UserAdmin):
    list_display = ('username', 'first_name', 'last_name', 'carrier_name', 'cycle_type')
    fieldsets = UserAdmin.fieldsets + (
        ('Driver Info', {
            'fields': (
                'license_number', 'carrier_name', 'carrier_address',
                'home_terminal_address', 'home_terminal_timezone',
                'cycle_type', 'truck_number', 'trailer_number', 'co_driver_name',
            ),
        }),
    )
