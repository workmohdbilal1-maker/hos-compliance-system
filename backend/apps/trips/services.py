import logging
import math
from datetime import timedelta
from decimal import Decimal

import requests
from django.conf import settings
from django.utils import timezone

from apps.hos.engine import (
    CycleType,
    DriverDay,
    DutyStatus,
    HOSCalculator,
    RouteSegment,
)
from apps.hos.models import DailyLog, DutyStatusLog
from apps.trips.models import Trip, TripStop

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Route Service -- wraps the OpenRouteService API
# ---------------------------------------------------------------------------

class RouteService:
    """
    Client for the OpenRouteService (ORS) Directions and Geocode APIs.

    Reads the API key from django.conf.settings.ORS_API_KEY.
    """

    BASE_URL = 'https://api.openrouteservice.org'

    def __init__(self):
        self.api_key = getattr(settings, 'ORS_API_KEY', '')

    # ---- Directions ----

    def get_route(self, coordinates: list[list[float]]) -> dict:
        """
        Fetch a route between two or more [lon, lat] coordinate pairs.

        Args:
            coordinates: List of [longitude, latitude] pairs, e.g.
                         [[-87.65, 41.85], [-73.97, 40.77]]

        Returns:
            Parsed JSON response from the ORS directions endpoint including
            geometry, distance (metres), and duration (seconds).

        Raises:
            requests.HTTPError: If the API returns a non-2xx status.
            ValueError: If the API key is not configured.
        """
        if not self.api_key:
            raise ValueError(
                'ORS_API_KEY is not configured. Set it in settings or '
                'the ORS_API_KEY environment variable.'
            )

        url = f'{self.BASE_URL}/v2/directions/driving-car'
        headers = {
            'Authorization': self.api_key,
            'Content-Type': 'application/json',
        }
        payload = {
            'coordinates': coordinates,
            'instructions': True,
            'geometry': True,
            'units': 'mi',
        }

        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()

    # ---- Geocode ----

    def geocode(self, query: str) -> dict:
        """
        Forward-geocode an address string to coordinates.

        Args:
            query: Free-form address or place name.

        Returns:
            Parsed JSON response from the ORS geocode endpoint.
        """
        if not self.api_key:
            raise ValueError('ORS_API_KEY is not configured.')

        url = f'{self.BASE_URL}/geocode/search'
        params = {
            'api_key': self.api_key,
            'text': query,
            'size': 5,
        }

        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        return response.json()


# ---------------------------------------------------------------------------
# Trip Planner Service -- orchestrates route + HOS + persistence
# ---------------------------------------------------------------------------

class TripPlannerService:
    """
    High-level service that:
      1. Calls the ORS route API to obtain the driving route.
      2. Builds RouteSegment objects for the HOS engine.
      3. Runs HOSCalculator.generate_trip_duty_logs to produce a
         compliant trip plan.
      4. Persists Trip, TripStop, and DutyStatusLog records.
    """

    # Metres-to-miles conversion factor
    METRES_TO_MILES = 0.000621371

    def __init__(self):
        self.route_service = RouteService()

    @staticmethod
    def _haversine_miles(lat1, lon1, lat2, lon2):
        """Great-circle distance between two lat/lon points in miles."""
        R = 3958.8  # Earth radius in miles
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        return R * 2 * math.asin(math.sqrt(a))

    def plan_trip(
        self,
        driver,
        current_location: dict,
        pickup_location: dict,
        dropoff_location: dict,
        cycle_hours_used: float = 0.0,
        options: dict | None = None,
    ) -> Trip:
        """
        End-to-end trip planning.

        Args:
            driver: The Driver (User) model instance.
            current_location: dict with keys lat, lng, name.
            pickup_location: dict with keys lat, lng, name.
            dropoff_location: dict with keys lat, lng, name.
            cycle_hours_used: Hours already used in the current cycle.
            options: Optional dict with short_haul_exemption, adverse_driving, etc.

        Returns:
            A saved Trip instance with stops and duty logs attached.
        """
        options = options or {}

        # ------------------------------------------------------------------
        # 1. Get route from ORS (current -> pickup -> dropoff)
        # ------------------------------------------------------------------
        coordinates = [
            [current_location['lng'], current_location['lat']],
            [pickup_location['lng'], pickup_location['lat']],
            [dropoff_location['lng'], dropoff_location['lat']],
        ]

        try:
            route_data = self.route_service.get_route(coordinates)
        except (requests.RequestException, ValueError) as exc:
            logger.error('Route API error: %s', exc)
            # Create trip without route data so it can be retried
            route_data = None

        # ------------------------------------------------------------------
        # 2. Parse route into segments
        # ------------------------------------------------------------------
        route_segments = []
        total_distance_miles = 0.0
        total_duration_hours = 0.0

        if route_data and 'routes' in route_data:
            route = route_data['routes'][0]
            summary = route.get('summary', {})
            total_distance_miles = summary.get('distance', 0)
            total_duration_hours = summary.get('duration', 0) / 3600

            legs = route.get('segments', route.get('legs', []))

            waypoints = [current_location, pickup_location, dropoff_location]
            for idx, leg in enumerate(legs):
                leg_distance = leg.get('distance', 0)
                leg_duration = leg.get('duration', 0) / 3600

                start_wp = waypoints[idx] if idx < len(waypoints) else waypoints[-1]
                end_wp = waypoints[idx + 1] if idx + 1 < len(waypoints) else waypoints[-1]

                route_segments.append(
                    RouteSegment(
                        start_location=start_wp.get('name', ''),
                        end_location=end_wp.get('name', ''),
                        distance_miles=leg_distance,
                        duration_hours=leg_duration,
                        start_lat=start_wp['lat'],
                        start_lon=start_wp['lng'],
                        end_lat=end_wp['lat'],
                        end_lon=end_wp['lng'],
                    )
                )
        else:
            # Fallback: estimate distance using Haversine formula (road
            # distance ~ 1.3x straight-line distance).
            for i, (start_wp, end_wp) in enumerate([
                (current_location, pickup_location),
                (pickup_location, dropoff_location),
            ]):
                straight_miles = self._haversine_miles(
                    start_wp['lat'], start_wp['lng'],
                    end_wp['lat'], end_wp['lng'],
                )
                est_miles = straight_miles * 1.3  # Road factor
                est_hours = est_miles / 55  # 55 mph avg
                total_distance_miles += est_miles
                total_duration_hours += est_hours

                route_segments.append(
                    RouteSegment(
                        start_location=start_wp.get('name', ''),
                        end_location=end_wp.get('name', ''),
                        distance_miles=est_miles,
                        duration_hours=est_hours,
                        start_lat=start_wp['lat'],
                        start_lon=start_wp['lng'],
                        end_lat=end_wp['lat'],
                        end_lon=end_wp['lng'],
                    )
                )

        # ------------------------------------------------------------------
        # 3. Build historical days for cycle calculation
        # ------------------------------------------------------------------
        try:
            cycle_type = CycleType(driver.cycle_type)
        except (ValueError, KeyError):
            cycle_type = CycleType.SEVENTY_EIGHT
        calculator = HOSCalculator(cycle_type=cycle_type)

        cycle_days = 8 if cycle_type == CycleType.SEVENTY_EIGHT else 7
        today = timezone.now().date()
        history_start = today - timedelta(days=cycle_days)

        daily_logs = DailyLog.objects.filter(
            driver=driver,
            date__gte=history_start,
            date__lt=today,
        ).order_by('-date')

        historical_days = []
        for dl in daily_logs:
            historical_days.append(
                DriverDay(
                    day_date=dl.date,
                    on_duty_hours=float(dl.driving_hours + dl.on_duty_hours),
                    driving_hours=float(dl.driving_hours),
                    off_duty_hours=float(dl.off_duty_hours),
                    sleeper_hours=float(dl.sleeper_hours),
                )
            )

        # ------------------------------------------------------------------
        # 4. Generate HOS-compliant trip plan
        # ------------------------------------------------------------------
        start_time = timezone.now()
        adverse_driving = options.get('adverse_driving', False)

        trip_plan = calculator.generate_trip_duty_logs(
            route_segments=route_segments,
            historical_days=historical_days,
            start_time=start_time,
            current_cycle_used=cycle_hours_used,
            adverse_driving=adverse_driving,
        )

        # ------------------------------------------------------------------
        # 5. Persist Trip
        # ------------------------------------------------------------------
        trip = Trip.objects.create(
            driver=driver,
            status='planning',
            current_location=current_location.get('name', ''),
            current_lat=Decimal(str(current_location['lat'])),
            current_lon=Decimal(str(current_location['lng'])),
            pickup_location=pickup_location.get('name', ''),
            pickup_lat=Decimal(str(pickup_location['lat'])),
            pickup_lon=Decimal(str(pickup_location['lng'])),
            dropoff_location=dropoff_location.get('name', ''),
            dropoff_lat=Decimal(str(dropoff_location['lat'])),
            dropoff_lon=Decimal(str(dropoff_location['lng'])),
            current_cycle_used=Decimal(str(cycle_hours_used)),
            route_data=route_data,
            total_distance_miles=(
                Decimal(str(round(total_distance_miles, 1)))
                if total_distance_miles else None
            ),
            estimated_duration_hours=(
                Decimal(str(round(total_duration_hours, 2)))
                if total_duration_hours else None
            ),
            short_haul_exemption=options.get('short_haul_exemption', False),
            adverse_driving=adverse_driving,
            sleeper_berth_split_first=options.get('sleeper_berth_split_first'),
            sleeper_berth_split_second=options.get('sleeper_berth_split_second'),
            total_trip_days=trip_plan.total_days,
            total_driving_hours=Decimal(str(round(trip_plan.total_driving_hours, 2))),
        )

        # ------------------------------------------------------------------
        # 6. Persist TripStops
        # ------------------------------------------------------------------
        stop_sequence = 0

        # Start stop
        TripStop.objects.create(
            trip=trip,
            stop_type='start',
            location_name=current_location.get('name', ''),
            lat=Decimal(str(current_location['lat'])),
            lon=Decimal(str(current_location['lng'])),
            arrival_time=start_time,
            departure_time=start_time,
            sequence=stop_sequence,
            duration_minutes=0,
        )
        stop_sequence += 1

        # Pickup stop
        # Find the first "Pickup / loading" entry for timing
        pickup_entry = next(
            (e for e in trip_plan.entries if 'Pickup' in (e.remarks or '')),
            None,
        )
        TripStop.objects.create(
            trip=trip,
            stop_type='pickup',
            location_name=pickup_location.get('name', ''),
            lat=Decimal(str(pickup_location['lat'])),
            lon=Decimal(str(pickup_location['lng'])),
            arrival_time=pickup_entry.start_time if pickup_entry else start_time,
            departure_time=pickup_entry.end_time if pickup_entry else start_time,
            sequence=stop_sequence,
            duration_minutes=60,
        )
        stop_sequence += 1

        # Rest/break stops from the plan
        for entry in trip_plan.entries:
            remarks = entry.remarks or ''
            if '10-hour off-duty rest' in remarks:
                TripStop.objects.create(
                    trip=trip,
                    stop_type='rest',
                    location_name=entry.location or 'Rest area',
                    lat=Decimal(str(entry.lat or 0)),
                    lon=Decimal(str(entry.lon or 0)),
                    arrival_time=entry.start_time,
                    departure_time=entry.end_time,
                    sequence=stop_sequence,
                    duration_minutes=600,
                )
                stop_sequence += 1
            elif '30-minute rest break' in remarks:
                TripStop.objects.create(
                    trip=trip,
                    stop_type='break',
                    location_name=entry.location or 'Break stop',
                    lat=Decimal(str(entry.lat or 0)),
                    lon=Decimal(str(entry.lon or 0)),
                    arrival_time=entry.start_time,
                    departure_time=entry.end_time,
                    sequence=stop_sequence,
                    duration_minutes=30,
                )
                stop_sequence += 1
            elif 'Fuel stop' in remarks:
                TripStop.objects.create(
                    trip=trip,
                    stop_type='fuel',
                    location_name=entry.location or 'Fuel station',
                    lat=Decimal(str(entry.lat or 0)),
                    lon=Decimal(str(entry.lon or 0)),
                    arrival_time=entry.start_time,
                    departure_time=entry.end_time,
                    sequence=stop_sequence,
                    duration_minutes=30,
                )
                stop_sequence += 1

        # Dropoff stop
        dropoff_entry = next(
            (e for e in trip_plan.entries if 'Dropoff' in (e.remarks or '')),
            None,
        )
        TripStop.objects.create(
            trip=trip,
            stop_type='dropoff',
            location_name=dropoff_location.get('name', ''),
            lat=Decimal(str(dropoff_location['lat'])),
            lon=Decimal(str(dropoff_location['lng'])),
            arrival_time=dropoff_entry.start_time if dropoff_entry else start_time,
            departure_time=dropoff_entry.end_time if dropoff_entry else start_time,
            sequence=stop_sequence,
            duration_minutes=60,
        )

        # ------------------------------------------------------------------
        # 7. Persist DutyStatusLog entries
        # ------------------------------------------------------------------
        duty_logs = []
        for entry in trip_plan.entries:
            duty_logs.append(
                DutyStatusLog(
                    driver=driver,
                    status=entry.status.value,
                    start_time=entry.start_time,
                    end_time=entry.end_time,
                    location_name=entry.location or '',
                    location_lat=(
                        Decimal(str(entry.lat)) if entry.lat is not None else None
                    ),
                    location_lon=(
                        Decimal(str(entry.lon)) if entry.lon is not None else None
                    ),
                    odometer=None,
                    remarks=entry.remarks or '',
                    trip=trip,
                )
            )
        DutyStatusLog.objects.bulk_create(duty_logs)

        return trip
