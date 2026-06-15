from django.contrib import admin

from apps.trips.models import Trip, TripStop


class TripStopInline(admin.TabularInline):
    model = TripStop
    extra = 0
    ordering = ('sequence',)
    readonly_fields = ('arrival_time', 'departure_time')


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'driver',
        'status',
        'current_location',
        'pickup_location',
        'dropoff_location',
        'total_distance_miles',
        'total_trip_days',
        'created_at',
    )
    list_filter = ('status', 'short_haul_exemption', 'adverse_driving')
    search_fields = (
        'driver__username',
        'current_location',
        'pickup_location',
        'dropoff_location',
    )
    raw_id_fields = ('driver',)
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    inlines = [TripStopInline]


@admin.register(TripStop)
class TripStopAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'trip',
        'stop_type',
        'location_name',
        'sequence',
        'arrival_time',
        'duration_minutes',
    )
    list_filter = ('stop_type',)
    search_fields = ('location_name',)
    raw_id_fields = ('trip',)
    ordering = ('trip', 'sequence')
