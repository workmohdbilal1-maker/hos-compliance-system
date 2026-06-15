import random
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import Driver
from apps.hos.models import DutyStatusLog, DailyLog
from apps.trips.models import Trip, TripStop


class Command(BaseCommand):
    help = "Seed the database with demo driver, trips, duty logs, and daily logs."

    def handle(self, *args, **options):
        self.stdout.write("=" * 60)
        self.stdout.write("  Seeding demo data...")
        self.stdout.write("=" * 60)

        driver = self._create_driver()
        self._create_daily_logs(driver)
        self._create_trip_1(driver)
        self._create_trip_2(driver)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("All demo data seeded successfully!"))
        self.stdout.write(f"  Login with: username=demo_driver  password=demo123")
        self.stdout.write("=" * 60)

    # ------------------------------------------------------------------
    # Driver
    # ------------------------------------------------------------------
    def _create_driver(self):
        driver, created = Driver.objects.get_or_create(
            username="demo_driver",
            defaults={
                "first_name": "John",
                "last_name": "Trucker",
                "email": "demo@spottertransport.com",
                "carrier_name": "Spotter Transport LLC",
                "carrier_address": "456 Carrier Blvd, Chicago, IL 60601",
                "home_terminal_address": "123 Main St, Chicago, IL",
                "home_terminal_timezone": "America/Chicago",
                "cycle_type": "70_8",
                "truck_number": "TRK-1234",
                "trailer_number": "TRL-5678",
                "co_driver_name": "",
                "license_number": "CDL-IL-2024-9876",
            },
        )

        if created:
            driver.set_password("demo123")
            driver.save()
            self.stdout.write(self.style.SUCCESS("[+] Created demo driver: demo_driver"))
        else:
            self.stdout.write(self.style.WARNING("[~] Demo driver already exists, skipping creation."))

        return driver

    # ------------------------------------------------------------------
    # 8 days of DailyLog history
    # ------------------------------------------------------------------
    def _create_daily_logs(self, driver):
        now = timezone.now()
        today = now.date()

        # Realistic varied daily data.  Sum of driving+on_duty ~ 50-60 hrs.
        daily_data = [
            # (days_ago, driving, on_duty, off_duty, sleeper, miles, from, to, doc)
            (7, Decimal("8.00"), Decimal("2.00"), Decimal("4.00"), Decimal("10.00"),
             Decimal("440.0"), "Chicago, IL", "Indianapolis, IN", "BOL-7701"),
            (6, Decimal("7.50"), Decimal("1.50"), Decimal("5.00"), Decimal("10.00"),
             Decimal("410.0"), "Indianapolis, IN", "Louisville, KY", "BOL-7702"),
            (5, Decimal("6.00"), Decimal("1.00"), Decimal("7.00"), Decimal("10.00"),
             Decimal("330.0"), "Louisville, KY", "Nashville, TN", "BOL-7703"),
            (4, Decimal("0.00"), Decimal("0.00"), Decimal("14.00"), Decimal("10.00"),
             Decimal("0.0"), "Nashville, TN", "Nashville, TN", ""),
            (3, Decimal("7.00"), Decimal("2.50"), Decimal("4.50"), Decimal("10.00"),
             Decimal("385.0"), "Nashville, TN", "Atlanta, GA", "BOL-7704"),
            (2, Decimal("8.50"), Decimal("1.50"), Decimal("4.00"), Decimal("10.00"),
             Decimal("470.0"), "Atlanta, GA", "Charlotte, NC", "BOL-7705"),
            (1, Decimal("5.50"), Decimal("1.00"), Decimal("7.50"), Decimal("10.00"),
             Decimal("300.0"), "Charlotte, NC", "Richmond, VA", "BOL-7706"),
            (0, Decimal("3.00"), Decimal("1.00"), Decimal("6.00"), Decimal("0.00"),
             Decimal("165.0"), "Richmond, VA", "Washington, DC", "BOL-7707"),
        ]

        created_count = 0
        for (days_ago, driving, on_duty, off_duty, sleeper,
             miles, from_loc, to_loc, doc) in daily_data:
            log_date = today - timedelta(days=days_ago)
            _, created = DailyLog.objects.get_or_create(
                driver=driver,
                date=log_date,
                defaults={
                    "driving_hours": driving,
                    "on_duty_hours": on_duty,
                    "off_duty_hours": off_duty,
                    "sleeper_hours": sleeper,
                    "total_miles": miles,
                    "from_location": from_loc,
                    "to_location": to_loc,
                    "shipping_doc": doc,
                },
            )
            if created:
                created_count += 1

        total_driving = sum(d[1] for d in daily_data)
        total_on_duty = sum(d[2] for d in daily_data)
        self.stdout.write(
            self.style.SUCCESS(
                f"[+] Created {created_count} daily logs "
                f"(driving={total_driving}h, on_duty={total_on_duty}h, "
                f"combined={total_driving + total_on_duty}h over 8 days)"
            )
        )

    # ------------------------------------------------------------------
    # Trip 1: New York -> Philadelphia -> Atlanta  (multi-day)
    # ------------------------------------------------------------------
    def _create_trip_1(self, driver):
        now = timezone.now()

        trip, created = Trip.objects.get_or_create(
            driver=driver,
            current_location="New York, NY",
            dropoff_location="Atlanta, GA",
            status="completed",
            defaults={
                "current_lat": Decimal("40.712776"),
                "current_lon": Decimal("-74.005974"),
                "pickup_location": "Philadelphia, PA",
                "pickup_lat": Decimal("39.952583"),
                "pickup_lon": Decimal("-75.165222"),
                "dropoff_lat": Decimal("33.748992"),
                "dropoff_lon": Decimal("-84.387985"),
                "current_cycle_used": Decimal("12.50"),
                "total_distance_miles": Decimal("874.0"),
                "estimated_duration_hours": Decimal("14.50"),
                "total_trip_days": 2,
                "total_driving_hours": Decimal("14.50"),
                "route_data": {
                    "waypoints": [
                        {"name": "New York, NY", "lat": 40.712776, "lon": -74.005974},
                        {"name": "Philadelphia, PA", "lat": 39.952583, "lon": -75.165222},
                        {"name": "Baltimore, MD", "lat": 39.290386, "lon": -76.612190},
                        {"name": "Charlotte, NC", "lat": 35.227085, "lon": -80.843124},
                        {"name": "Atlanta, GA", "lat": 33.748992, "lon": -84.387985},
                    ],
                    "total_miles": 874,
                    "overview": "I-95 S to I-85 S",
                },
            },
        )

        if not created:
            self.stdout.write(self.style.WARNING("[~] Trip 1 (NY->ATL) already exists, skipping."))
            return

        self.stdout.write(self.style.SUCCESS("[+] Created Trip 1: New York -> Philadelphia -> Atlanta"))

        # ----- Trip Stops -----
        trip_start = now - timedelta(days=3)

        stops_data = [
            {
                "stop_type": "start",
                "location_name": "New York, NY",
                "lat": Decimal("40.712776"),
                "lon": Decimal("-74.005974"),
                "arrival_time": trip_start,
                "departure_time": trip_start + timedelta(minutes=30),
                "sequence": 1,
                "duration_minutes": 30,
            },
            {
                "stop_type": "pickup",
                "location_name": "Philadelphia, PA - Warehouse District",
                "lat": Decimal("39.952583"),
                "lon": Decimal("-75.165222"),
                "arrival_time": trip_start + timedelta(hours=2),
                "departure_time": trip_start + timedelta(hours=2, minutes=45),
                "sequence": 2,
                "duration_minutes": 45,
            },
            {
                "stop_type": "break",
                "location_name": "Baltimore, MD - Truck Stop",
                "lat": Decimal("39.290386"),
                "lon": Decimal("-76.612190"),
                "arrival_time": trip_start + timedelta(hours=4, minutes=30),
                "departure_time": trip_start + timedelta(hours=5),
                "sequence": 3,
                "duration_minutes": 30,
            },
            {
                "stop_type": "rest",
                "location_name": "Charlotte, NC - Rest Area",
                "lat": Decimal("35.227085"),
                "lon": Decimal("-80.843124"),
                "arrival_time": trip_start + timedelta(hours=12),
                "departure_time": trip_start + timedelta(hours=22),
                "sequence": 4,
                "duration_minutes": 600,
            },
            {
                "stop_type": "dropoff",
                "location_name": "Atlanta, GA - Distribution Center",
                "lat": Decimal("33.748992"),
                "lon": Decimal("-84.387985"),
                "arrival_time": trip_start + timedelta(hours=26),
                "departure_time": trip_start + timedelta(hours=26, minutes=30),
                "sequence": 5,
                "duration_minutes": 30,
            },
        ]

        for stop_kwargs in stops_data:
            TripStop.objects.create(trip=trip, **stop_kwargs)
        self.stdout.write(f"    Created {len(stops_data)} trip stops")

        # ----- Duty Status Logs for Trip 1 -----
        duty_logs = [
            # Day 1: Pre-trip inspection
            {
                "status": "on_duty_not_driving",
                "start_time": trip_start,
                "end_time": trip_start + timedelta(minutes=30),
                "location_name": "New York, NY",
                "location_lat": Decimal("40.712776"),
                "location_lon": Decimal("-74.005974"),
                "remarks": "Pre-trip inspection",
            },
            # Day 1: Drive to Philadelphia
            {
                "status": "driving",
                "start_time": trip_start + timedelta(minutes=30),
                "end_time": trip_start + timedelta(hours=2),
                "location_name": "I-95 S - New York to Philadelphia",
                "location_lat": Decimal("40.220100"),
                "location_lon": Decimal("-74.763500"),
                "remarks": "En route to pickup",
            },
            # Day 1: Loading at pickup
            {
                "status": "on_duty_not_driving",
                "start_time": trip_start + timedelta(hours=2),
                "end_time": trip_start + timedelta(hours=2, minutes=45),
                "location_name": "Philadelphia, PA - Warehouse District",
                "location_lat": Decimal("39.952583"),
                "location_lon": Decimal("-75.165222"),
                "remarks": "Loading freight",
            },
            # Day 1: Drive to Baltimore
            {
                "status": "driving",
                "start_time": trip_start + timedelta(hours=2, minutes=45),
                "end_time": trip_start + timedelta(hours=4, minutes=30),
                "location_name": "I-95 S - Philadelphia to Baltimore",
                "location_lat": Decimal("39.590000"),
                "location_lon": Decimal("-75.900000"),
                "remarks": "",
            },
            # Day 1: 30-minute break
            {
                "status": "off_duty",
                "start_time": trip_start + timedelta(hours=4, minutes=30),
                "end_time": trip_start + timedelta(hours=5),
                "location_name": "Baltimore, MD - Truck Stop",
                "location_lat": Decimal("39.290386"),
                "location_lon": Decimal("-76.612190"),
                "remarks": "30-min break",
            },
            # Day 1: Drive to Charlotte
            {
                "status": "driving",
                "start_time": trip_start + timedelta(hours=5),
                "end_time": trip_start + timedelta(hours=12),
                "location_name": "I-85 S - Baltimore to Charlotte",
                "location_lat": Decimal("37.540700"),
                "location_lon": Decimal("-77.436000"),
                "remarks": "",
            },
            # Day 1: 10-hour rest in Charlotte
            {
                "status": "sleeper_berth",
                "start_time": trip_start + timedelta(hours=12),
                "end_time": trip_start + timedelta(hours=22),
                "location_name": "Charlotte, NC - Rest Area",
                "location_lat": Decimal("35.227085"),
                "location_lon": Decimal("-80.843124"),
                "remarks": "10-hour rest period",
            },
            # Day 2: Pre-trip inspection
            {
                "status": "on_duty_not_driving",
                "start_time": trip_start + timedelta(hours=22),
                "end_time": trip_start + timedelta(hours=22, minutes=15),
                "location_name": "Charlotte, NC - Rest Area",
                "location_lat": Decimal("35.227085"),
                "location_lon": Decimal("-80.843124"),
                "remarks": "Pre-trip inspection day 2",
            },
            # Day 2: Drive to Atlanta
            {
                "status": "driving",
                "start_time": trip_start + timedelta(hours=22, minutes=15),
                "end_time": trip_start + timedelta(hours=26),
                "location_name": "I-85 S - Charlotte to Atlanta",
                "location_lat": Decimal("34.200000"),
                "location_lon": Decimal("-82.150000"),
                "remarks": "Final leg to delivery",
            },
            # Day 2: Unloading
            {
                "status": "on_duty_not_driving",
                "start_time": trip_start + timedelta(hours=26),
                "end_time": trip_start + timedelta(hours=26, minutes=30),
                "location_name": "Atlanta, GA - Distribution Center",
                "location_lat": Decimal("33.748992"),
                "location_lon": Decimal("-84.387985"),
                "remarks": "Unloading freight at destination",
            },
            # Day 2: Off duty after delivery
            {
                "status": "off_duty",
                "start_time": trip_start + timedelta(hours=26, minutes=30),
                "end_time": trip_start + timedelta(hours=36, minutes=30),
                "location_name": "Atlanta, GA",
                "location_lat": Decimal("33.748992"),
                "location_lon": Decimal("-84.387985"),
                "remarks": "Off duty after delivery",
            },
        ]

        for log_kwargs in duty_logs:
            DutyStatusLog.objects.create(driver=driver, trip=trip, **log_kwargs)
        self.stdout.write(f"    Created {len(duty_logs)} duty status logs for Trip 1")

    # ------------------------------------------------------------------
    # Trip 2: Chicago -> Indianapolis -> Nashville (single-day, shorter)
    # ------------------------------------------------------------------
    def _create_trip_2(self, driver):
        now = timezone.now()

        trip, created = Trip.objects.get_or_create(
            driver=driver,
            current_location="Chicago, IL",
            dropoff_location="Nashville, TN",
            status="completed",
            defaults={
                "current_lat": Decimal("41.878113"),
                "current_lon": Decimal("-87.629799"),
                "pickup_location": "Indianapolis, IN",
                "pickup_lat": Decimal("39.768403"),
                "pickup_lon": Decimal("-86.158068"),
                "dropoff_lat": Decimal("36.162663"),
                "dropoff_lon": Decimal("-86.781601"),
                "current_cycle_used": Decimal("22.00"),
                "total_distance_miles": Decimal("468.0"),
                "estimated_duration_hours": Decimal("7.50"),
                "total_trip_days": 1,
                "total_driving_hours": Decimal("7.50"),
                "route_data": {
                    "waypoints": [
                        {"name": "Chicago, IL", "lat": 41.878113, "lon": -87.629799},
                        {"name": "Indianapolis, IN", "lat": 39.768403, "lon": -86.158068},
                        {"name": "Nashville, TN", "lat": 36.162663, "lon": -86.781601},
                    ],
                    "total_miles": 468,
                    "overview": "I-65 S",
                },
            },
        )

        if not created:
            self.stdout.write(self.style.WARNING("[~] Trip 2 (CHI->NSH) already exists, skipping."))
            return

        self.stdout.write(self.style.SUCCESS("[+] Created Trip 2: Chicago -> Indianapolis -> Nashville"))

        # ----- Trip Stops -----
        trip_start = now - timedelta(days=6, hours=6)

        stops_data = [
            {
                "stop_type": "start",
                "location_name": "Chicago, IL",
                "lat": Decimal("41.878113"),
                "lon": Decimal("-87.629799"),
                "arrival_time": trip_start,
                "departure_time": trip_start + timedelta(minutes=20),
                "sequence": 1,
                "duration_minutes": 20,
            },
            {
                "stop_type": "pickup",
                "location_name": "Indianapolis, IN - Freight Terminal",
                "lat": Decimal("39.768403"),
                "lon": Decimal("-86.158068"),
                "arrival_time": trip_start + timedelta(hours=3),
                "departure_time": trip_start + timedelta(hours=3, minutes=40),
                "sequence": 2,
                "duration_minutes": 40,
            },
            {
                "stop_type": "break",
                "location_name": "Seymour, IN - Travel Plaza",
                "lat": Decimal("38.959200"),
                "lon": Decimal("-85.890300"),
                "arrival_time": trip_start + timedelta(hours=4, minutes=30),
                "departure_time": trip_start + timedelta(hours=5),
                "sequence": 3,
                "duration_minutes": 30,
            },
            {
                "stop_type": "dropoff",
                "location_name": "Nashville, TN - Music City Depot",
                "lat": Decimal("36.162663"),
                "lon": Decimal("-86.781601"),
                "arrival_time": trip_start + timedelta(hours=7, minutes=30),
                "departure_time": trip_start + timedelta(hours=8),
                "sequence": 4,
                "duration_minutes": 30,
            },
        ]

        for stop_kwargs in stops_data:
            TripStop.objects.create(trip=trip, **stop_kwargs)
        self.stdout.write(f"    Created {len(stops_data)} trip stops")

        # ----- Duty Status Logs for Trip 2 -----
        duty_logs = [
            # Pre-trip
            {
                "status": "on_duty_not_driving",
                "start_time": trip_start,
                "end_time": trip_start + timedelta(minutes=20),
                "location_name": "Chicago, IL",
                "location_lat": Decimal("41.878113"),
                "location_lon": Decimal("-87.629799"),
                "remarks": "Pre-trip inspection",
            },
            # Drive Chicago to Indianapolis
            {
                "status": "driving",
                "start_time": trip_start + timedelta(minutes=20),
                "end_time": trip_start + timedelta(hours=3),
                "location_name": "I-65 S - Chicago to Indianapolis",
                "location_lat": Decimal("40.750000"),
                "location_lon": Decimal("-86.950000"),
                "remarks": "Southbound on I-65",
            },
            # Loading at Indianapolis
            {
                "status": "on_duty_not_driving",
                "start_time": trip_start + timedelta(hours=3),
                "end_time": trip_start + timedelta(hours=3, minutes=40),
                "location_name": "Indianapolis, IN - Freight Terminal",
                "location_lat": Decimal("39.768403"),
                "location_lon": Decimal("-86.158068"),
                "remarks": "Loading freight",
            },
            # Drive Indianapolis toward Seymour
            {
                "status": "driving",
                "start_time": trip_start + timedelta(hours=3, minutes=40),
                "end_time": trip_start + timedelta(hours=4, minutes=30),
                "location_name": "I-65 S - Indianapolis to Seymour",
                "location_lat": Decimal("39.300000"),
                "location_lon": Decimal("-86.050000"),
                "remarks": "",
            },
            # 30-minute break
            {
                "status": "off_duty",
                "start_time": trip_start + timedelta(hours=4, minutes=30),
                "end_time": trip_start + timedelta(hours=5),
                "location_name": "Seymour, IN - Travel Plaza",
                "location_lat": Decimal("38.959200"),
                "location_lon": Decimal("-85.890300"),
                "remarks": "30-min break",
            },
            # Drive Seymour to Nashville
            {
                "status": "driving",
                "start_time": trip_start + timedelta(hours=5),
                "end_time": trip_start + timedelta(hours=7, minutes=30),
                "location_name": "I-65 S - Seymour to Nashville",
                "location_lat": Decimal("37.500000"),
                "location_lon": Decimal("-86.400000"),
                "remarks": "Final leg to Nashville",
            },
            # Unloading
            {
                "status": "on_duty_not_driving",
                "start_time": trip_start + timedelta(hours=7, minutes=30),
                "end_time": trip_start + timedelta(hours=8),
                "location_name": "Nashville, TN - Music City Depot",
                "location_lat": Decimal("36.162663"),
                "location_lon": Decimal("-86.781601"),
                "remarks": "Unloading freight",
            },
            # Off duty
            {
                "status": "off_duty",
                "start_time": trip_start + timedelta(hours=8),
                "end_time": trip_start + timedelta(hours=18),
                "location_name": "Nashville, TN",
                "location_lat": Decimal("36.162663"),
                "location_lon": Decimal("-86.781601"),
                "remarks": "Off duty after delivery",
            },
        ]

        for log_kwargs in duty_logs:
            DutyStatusLog.objects.create(driver=driver, trip=trip, **log_kwargs)
        self.stdout.write(f"    Created {len(duty_logs)} duty status logs for Trip 2")
