from django.contrib import admin

from apps.hos.models import DailyLog, DutyStatusLog


@admin.register(DutyStatusLog)
class DutyStatusLogAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'driver',
        'status',
        'start_time',
        'end_time',
        'location_name',
        'trip',
    )
    list_filter = ('status', 'is_personal_conveyance', 'is_yard_move')
    search_fields = ('driver__username', 'location_name', 'remarks')
    raw_id_fields = ('driver', 'trip')
    date_hierarchy = 'start_time'
    ordering = ('-start_time',)


@admin.register(DailyLog)
class DailyLogAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'driver',
        'date',
        'driving_hours',
        'on_duty_hours',
        'off_duty_hours',
        'sleeper_hours',
        'total_miles',
    )
    list_filter = ('date',)
    search_fields = ('driver__username',)
    raw_id_fields = ('driver',)
    date_hierarchy = 'date'
    ordering = ('-date',)
