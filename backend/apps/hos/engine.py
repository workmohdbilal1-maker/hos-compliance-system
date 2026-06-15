"""
Pure Python HOS (Hours of Service) compliance engine.

Implements FMCSA regulations per the Interstate Truck Driver's Guide to HOS (April 2022).
No Django dependencies -- uses only standard library + dataclasses.

Rules implemented:
  - 14-Hour Driving Window (§ 395.3(a)(2))
  - 11-Hour Driving Limit (§ 395.3(a)(3))
  - 30-Minute Rest Break (§ 395.3(a)(3)(ii))
  - 60/70-Hour On-Duty Limit (§ 395.3(b))
  - 34-Hour Restart (§ 395.3(c))
  - Sleeper Berth Provision (§ 395.1(g))
  - Adverse Driving Conditions Exception (§ 395.1(b)(1))
  - CDL Short-Haul Exception (§ 395.1(e)(1))
  - Non-CDL Short-Haul Exception (§ 395.1(e)(2))
  - 16-Hour Short-Haul Exception (§ 395.1(o))
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, date
from enum import Enum
from typing import Optional


class DutyStatus(str, Enum):
    OFF_DUTY = "off_duty"
    SLEEPER_BERTH = "sleeper_berth"
    DRIVING = "driving"
    ON_DUTY_NOT_DRIVING = "on_duty_not_driving"


class CycleType(str, Enum):
    SIXTY_SEVEN = "60_7"    # 60 hours in 7 days
    SEVENTY_EIGHT = "70_8"  # 70 hours in 8 days


@dataclass
class DutyStatusEntry:
    """A single period of a specific duty status."""
    status: DutyStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    location: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    odometer: Optional[float] = None
    remarks: Optional[str] = None

    @property
    def duration(self) -> timedelta:
        if self.end_time is None:
            return timedelta(0)
        return self.end_time - self.start_time

    @property
    def duration_hours(self) -> float:
        return self.duration.total_seconds() / 3600


@dataclass
class DriverDay:
    """One calendar day of duty status summaries (used for historical rolling calculations)."""
    day_date: date
    on_duty_hours: float = 0.0  # driving + on-duty not driving
    driving_hours: float = 0.0
    off_duty_hours: float = 0.0
    sleeper_hours: float = 0.0


@dataclass
class HOSViolation:
    rule: str
    description: str
    violation_time: Optional[datetime] = None
    severity: str = "violation"  # "violation" or "warning"


@dataclass
class RuleCheckResult:
    used: timedelta
    limit: timedelta
    remaining: timedelta
    violated: bool
    explanation: str = ""

    @property
    def remaining_hours(self) -> float:
        return max(0, self.remaining.total_seconds() / 3600)


@dataclass
class HOSStatus:
    """Comprehensive HOS compliance status for a driver."""
    driving_hours_used: float
    driving_hours_remaining: float
    window_hours_used: float
    window_hours_remaining: float
    break_hours_driving_since_last: float
    break_required: bool
    cycle_hours_used: float
    cycle_hours_remaining: float
    cycle_type: CycleType
    can_drive: bool
    violations: list[HOSViolation] = field(default_factory=list)
    current_duty_status: Optional[DutyStatus] = None
    window_start: Optional[datetime] = None
    window_end: Optional[datetime] = None
    next_break_required_by: Optional[datetime] = None
    gain_time_at: Optional[datetime] = None  # When hours become available again
    explanations: list[str] = field(default_factory=list)


@dataclass
class RouteSegment:
    """A segment of a route between two points."""
    start_location: str
    end_location: str
    distance_miles: float
    duration_hours: float
    start_lat: float = 0.0
    start_lon: float = 0.0
    end_lat: float = 0.0
    end_lon: float = 0.0


@dataclass
class TripPlan:
    """Complete trip plan with duty logs, stops, and HOS compliance info."""
    entries: list[DutyStatusEntry]
    total_days: int
    total_driving_hours: float
    total_distance_miles: float
    violations: list[HOSViolation]
    daily_summaries: list[dict]
    explanations: list[str]


# ---------------------------------------------------------------------------
# HOS Calculator
# ---------------------------------------------------------------------------

class HOSCalculator:
    """
    Stateless HOS compliance calculator.

    All methods accept log entries and return computed results.
    Implements FMCSA property-carrier HOS rules (April 2022).
    """

    # Constants from FMCSA regulations
    MAX_DRIVING_HOURS = timedelta(hours=11)
    MAX_WINDOW_HOURS = timedelta(hours=14)
    REQUIRED_OFF_DUTY = timedelta(hours=10)
    BREAK_DRIVING_THRESHOLD = timedelta(hours=8)
    REQUIRED_BREAK = timedelta(minutes=30)
    RESTART_DURATION = timedelta(hours=34)

    # Adverse driving extensions
    ADVERSE_DRIVING_EXTENSION = timedelta(hours=2)
    ADVERSE_MAX_DRIVING = timedelta(hours=13)
    ADVERSE_MAX_WINDOW = timedelta(hours=16)

    # Default average speed for trip planning
    DEFAULT_AVG_SPEED_MPH = 55

    def __init__(self, cycle_type: CycleType = CycleType.SEVENTY_EIGHT):
        self.cycle_type = cycle_type
        if cycle_type == CycleType.SIXTY_SEVEN:
            self.cycle_limit = timedelta(hours=60)
            self.cycle_days = 7
        else:
            self.cycle_limit = timedelta(hours=70)
            self.cycle_days = 8

    # ----- Helper methods -----

    @staticmethod
    def _is_off_duty(status: DutyStatus) -> bool:
        return status in (DutyStatus.OFF_DUTY, DutyStatus.SLEEPER_BERTH)

    @staticmethod
    def _is_on_duty(status: DutyStatus) -> bool:
        return status in (DutyStatus.DRIVING, DutyStatus.ON_DUTY_NOT_DRIVING)

    @staticmethod
    def _is_non_driving(status: DutyStatus) -> bool:
        return status != DutyStatus.DRIVING

    def _find_last_qualifying_rest(
        self, entries: list[DutyStatusEntry]
    ) -> Optional[datetime]:
        """
        Find the end time of the most recent qualifying rest period.

        A qualifying rest is 10+ consecutive hours of off-duty or sleeper berth time
        (per § 395.3(a)(1)).
        """
        if not entries:
            return None

        # Walk entries in reverse to find the most recent qualifying rest
        consecutive_off = timedelta(0)
        rest_end = None

        for entry in reversed(entries):
            if self._is_off_duty(entry.status):
                if rest_end is None:
                    rest_end = entry.end_time or entry.start_time
                consecutive_off += entry.duration
                if consecutive_off >= self.REQUIRED_OFF_DUTY:
                    return rest_end
            else:
                consecutive_off = timedelta(0)
                rest_end = None

        # Check if the earliest entries form a qualifying rest
        if consecutive_off >= self.REQUIRED_OFF_DUTY and rest_end:
            return rest_end

        return None

    # ----- Core Rule Checks -----

    def check_14_hour_window(
        self,
        entries: list[DutyStatusEntry],
        current_time: datetime,
        adverse_driving: bool = False,
    ) -> RuleCheckResult:
        """
        14-Hour Driving Window (§ 395.3(a)(2)).

        The 14 consecutive hour window begins when the driver starts any kind of work
        after 10+ consecutive off-duty hours. Cannot drive after the window expires,
        but can do non-driving work.

        The window does NOT pause for off-duty time during the day.
        """
        max_window = self.ADVERSE_MAX_WINDOW if adverse_driving else self.MAX_WINDOW_HOURS

        last_rest_end = self._find_last_qualifying_rest(entries)

        if last_rest_end is None:
            # No qualifying rest found; assume window started at first on-duty entry
            on_duty_entries = [e for e in entries if self._is_on_duty(e.status)]
            if not on_duty_entries:
                return RuleCheckResult(
                    used=timedelta(0),
                    limit=max_window,
                    remaining=max_window,
                    violated=False,
                    explanation="No on-duty time found; full window available.",
                )
            window_start = on_duty_entries[0].start_time
        else:
            # Window starts at first on-duty entry after the rest
            post_rest = [e for e in entries
                         if e.start_time >= last_rest_end and self._is_on_duty(e.status)]
            if not post_rest:
                return RuleCheckResult(
                    used=timedelta(0),
                    limit=max_window,
                    remaining=max_window,
                    violated=False,
                    explanation="Driver has not started work after qualifying rest.",
                )
            window_start = post_rest[0].start_time

        elapsed = current_time - window_start
        remaining = max_window - elapsed

        return RuleCheckResult(
            used=elapsed,
            limit=max_window,
            remaining=max(timedelta(0), remaining),
            violated=elapsed > max_window,
            explanation=f"Window started at {window_start.strftime('%H:%M')}. "
                        f"{elapsed.total_seconds()/3600:.1f}h elapsed of {max_window.total_seconds()/3600:.0f}h.",
        )

    def check_11_hour_driving(
        self,
        entries: list[DutyStatusEntry],
        adverse_driving: bool = False,
    ) -> RuleCheckResult:
        """
        11-Hour Driving Limit (§ 395.3(a)(3)).

        Max 11 hours of driving within the 14-hour window after a qualifying
        10-hour rest. Resets after 10 consecutive off-duty hours.
        """
        max_driving = self.ADVERSE_MAX_DRIVING if adverse_driving else self.MAX_DRIVING_HOURS

        last_rest_end = self._find_last_qualifying_rest(entries)

        driving_total = timedelta(0)
        for entry in entries:
            if last_rest_end and entry.start_time < last_rest_end:
                continue
            if entry.status == DutyStatus.DRIVING:
                driving_total += entry.duration

        remaining = max_driving - driving_total

        return RuleCheckResult(
            used=driving_total,
            limit=max_driving,
            remaining=max(timedelta(0), remaining),
            violated=driving_total > max_driving,
            explanation=f"Driven {driving_total.total_seconds()/3600:.1f}h of "
                        f"{max_driving.total_seconds()/3600:.0f}h limit.",
        )

    def check_30_min_break(
        self,
        entries: list[DutyStatusEntry],
        current_time: datetime,
        short_haul_exempt: bool = False,
    ) -> RuleCheckResult:
        """
        30-Minute Rest Break (§ 395.3(a)(3)(ii)).

        Must take 30 consecutive minutes of non-driving time after 8 cumulative
        driving hours. The break can be off-duty, on-duty-not-driving, or sleeper berth.

        Consecutive periods of different non-driving statuses count if contiguous.

        Not required for short-haul exception drivers.
        """
        if short_haul_exempt:
            return RuleCheckResult(
                used=timedelta(0),
                limit=self.BREAK_DRIVING_THRESHOLD,
                remaining=self.BREAK_DRIVING_THRESHOLD,
                violated=False,
                explanation="Short-haul exempt from 30-minute break requirement.",
            )

        last_rest_end = self._find_last_qualifying_rest(entries)
        cumulative_driving = timedelta(0)

        # Find relevant entries (after last qualifying rest)
        relevant = [e for e in entries
                    if not last_rest_end or e.start_time >= last_rest_end]

        for entry in relevant:
            if entry.status == DutyStatus.DRIVING:
                cumulative_driving += entry.duration
            elif self._is_non_driving(entry.status) and entry.duration >= self.REQUIRED_BREAK:
                # This consecutive non-driving period qualifies as a break
                cumulative_driving = timedelta(0)

        # Also check for consecutive non-driving periods that together >= 30 min
        # Walk through and find consecutive non-driving blocks
        cumulative_driving = timedelta(0)
        consecutive_non_driving = timedelta(0)

        for entry in relevant:
            if entry.status == DutyStatus.DRIVING:
                consecutive_non_driving = timedelta(0)
                cumulative_driving += entry.duration
            else:
                consecutive_non_driving += entry.duration
                if consecutive_non_driving >= self.REQUIRED_BREAK:
                    cumulative_driving = timedelta(0)
                    consecutive_non_driving = timedelta(0)

        remaining = self.BREAK_DRIVING_THRESHOLD - cumulative_driving

        return RuleCheckResult(
            used=cumulative_driving,
            limit=self.BREAK_DRIVING_THRESHOLD,
            remaining=max(timedelta(0), remaining),
            violated=cumulative_driving > self.BREAK_DRIVING_THRESHOLD,
            explanation=f"Driven {cumulative_driving.total_seconds()/3600:.1f}h since last qualifying break.",
        )

    def check_cycle_limit(
        self,
        historical_days: list[DriverDay],
        current_day_on_duty: float = 0.0,
    ) -> RuleCheckResult:
        """
        60/70-Hour On-Duty Limit (§ 395.3(b)).

        Rolling 7-day (60hr) or 8-day (70hr) total on-duty limit.
        Oldest day drops off each new day.
        Violation only if driving past the limit.

        Uses the FMCSA rolling calculation method (page 10-11 of guide).
        """
        # Sum on-duty hours for the relevant number of past days
        days_to_use = sorted(historical_days, key=lambda d: d.day_date, reverse=True)
        days_to_use = days_to_use[:self.cycle_days]

        total_on_duty = sum(d.on_duty_hours for d in days_to_use) + current_day_on_duty
        total_td = timedelta(hours=total_on_duty)
        remaining = self.cycle_limit - total_td

        return RuleCheckResult(
            used=total_td,
            limit=self.cycle_limit,
            remaining=max(timedelta(0), remaining),
            violated=total_td > self.cycle_limit,
            explanation=f"Cycle: {total_on_duty:.1f}h on-duty in last {self.cycle_days} days. "
                        f"Limit: {self.cycle_limit.total_seconds()/3600:.0f}h.",
        )

    def check_34_hour_restart(
        self, entries: list[DutyStatusEntry]
    ) -> tuple[bool, Optional[datetime], Optional[datetime]]:
        """
        34-Hour Restart (§ 395.3(c)).

        34+ consecutive hours off duty resets the weekly cycle to zero.
        Can use sleeper berth or off-duty combination.
        Optional, not mandatory.

        Returns: (restart_found, restart_start, restart_end)
        """
        if not entries:
            return False, None, None

        consecutive_off_start = None
        consecutive_off = timedelta(0)
        best_restart = None

        for entry in entries:
            if self._is_off_duty(entry.status):
                if consecutive_off_start is None:
                    consecutive_off_start = entry.start_time
                consecutive_off += entry.duration
                if consecutive_off >= self.RESTART_DURATION:
                    end_time = entry.end_time or entry.start_time + entry.duration
                    best_restart = (consecutive_off_start, end_time)
            else:
                consecutive_off = timedelta(0)
                consecutive_off_start = None

        if best_restart:
            return True, best_restart[0], best_restart[1]
        return False, None, None

    def check_sleeper_berth_split(
        self, entries: list[DutyStatusEntry]
    ) -> tuple[bool, Optional[timedelta], Optional[timedelta]]:
        """
        Sleeper Berth Provision (§ 395.1(g)).

        Three ways to satisfy the 10-hour off-duty requirement:
        1. 10 consecutive hours in sleeper berth (full reset)
        2. 7hr sleeper + up to 3hr passenger seat = 10hr off-duty
        3. Split: one period >= 7hr sleeper + one period >= 2hr (sleeper or off-duty),
           totaling >= 10hr. Neither period counts against 14-hour window.

        Returns: (split_valid, driving_time_available, window_time_available)
        """
        if not entries:
            return False, None, None

        # Find qualifying sleeper berth periods
        qualifying_7hr = []  # Periods >= 7 hours in sleeper berth
        qualifying_2hr = []  # Periods >= 2 hours in sleeper berth or off-duty

        for entry in entries:
            if entry.status == DutyStatus.SLEEPER_BERTH and entry.duration >= timedelta(hours=7):
                qualifying_7hr.append(entry)
            if self._is_off_duty(entry.status) and entry.duration >= timedelta(hours=2):
                qualifying_2hr.append(entry)

        # Check for valid pair (one >= 7hr + one >= 2hr, totaling >= 10hr)
        for long_break in qualifying_7hr:
            for short_break in qualifying_2hr:
                if long_break is short_break:
                    continue
                total = long_break.duration + short_break.duration
                if total >= timedelta(hours=10):
                    # Valid split pair found
                    # Calculate remaining driving/window time excluding paired periods
                    return True, self.MAX_DRIVING_HOURS, self.MAX_WINDOW_HOURS

        return False, None, None

    def check_cdl_short_haul(
        self,
        distance_miles: float,
        entries: list[DutyStatusEntry],
        returns_to_start: bool = True,
    ) -> tuple[bool, str]:
        """
        CDL Short-Haul Exception (§ 395.1(e)(1)).

        Within 150 air-miles, return to same location, 14hr duty period,
        10hr off between. No ELD/30-min break required.
        """
        AIR_MILE_LIMIT = 150 * 1.15  # ~172.5 statute miles

        if distance_miles > AIR_MILE_LIMIT:
            return False, f"Distance {distance_miles:.0f} mi exceeds 150 air-mile radius."
        if not returns_to_start:
            return False, "Driver must return to normal work reporting location."
        return True, "Qualifies for CDL short-haul exception."

    def check_16_hour_short_haul(
        self,
        entries: list[DutyStatusEntry],
        used_this_week: bool = False,
    ) -> tuple[bool, str]:
        """
        16-Hour Short-Haul Exception (§ 395.1(o)).

        Extends 14hr window to 16hr, once per 7 consecutive days.
        Must return to work location.
        """
        if used_this_week:
            return False, "16-hour exception already used this 7-day period."
        return True, "16-hour short-haul exception available."

    # ----- Composite Status Calculator -----

    def calculate_hos_status(
        self,
        entries: list[DutyStatusEntry],
        historical_days: list[DriverDay],
        current_time: datetime,
        adverse_driving: bool = False,
        short_haul_exempt: bool = False,
    ) -> HOSStatus:
        """
        Master compliance check: runs all rule checks and returns comprehensive status.
        """
        violations = []
        explanations = []

        # 14-Hour Window
        window = self.check_14_hour_window(entries, current_time, adverse_driving)
        if window.violated:
            violations.append(HOSViolation(
                rule="14_hour_window",
                description=f"14-hour driving window exceeded. {window.explanation}",
                violation_time=current_time,
            ))
        explanations.append(f"Window: {window.explanation}")

        # 11-Hour Driving
        driving = self.check_11_hour_driving(entries, adverse_driving)
        if driving.violated:
            violations.append(HOSViolation(
                rule="11_hour_driving",
                description=f"11-hour driving limit exceeded. {driving.explanation}",
                violation_time=current_time,
            ))
        explanations.append(f"Driving: {driving.explanation}")

        # 30-Minute Break
        break_check = self.check_30_min_break(entries, current_time, short_haul_exempt)
        if break_check.violated:
            violations.append(HOSViolation(
                rule="30_min_break",
                description=f"30-minute break required. {break_check.explanation}",
                violation_time=current_time,
                severity="warning",
            ))
        explanations.append(f"Break: {break_check.explanation}")

        # Cycle Limit
        # Calculate today's on-duty time
        last_rest_end = self._find_last_qualifying_rest(entries)
        today_on_duty = 0.0
        for entry in entries:
            if last_rest_end and entry.start_time < last_rest_end:
                continue
            if self._is_on_duty(entry.status):
                today_on_duty += entry.duration_hours

        cycle = self.check_cycle_limit(historical_days, today_on_duty)
        if cycle.violated:
            violations.append(HOSViolation(
                rule="cycle_limit",
                description=f"Cycle limit exceeded. {cycle.explanation}",
                violation_time=current_time,
            ))
        explanations.append(f"Cycle: {cycle.explanation}")

        can_drive = (
            not window.violated
            and not driving.violated
            and not break_check.violated
            and not cycle.violated
        )

        # Determine current duty status
        current_status = None
        if entries:
            current_status = entries[-1].status

        # Window timing
        window_start = None
        window_end = None
        if entries:
            on_duty = [e for e in entries if self._is_on_duty(e.status)]
            if on_duty:
                if last_rest_end:
                    post_rest = [e for e in on_duty if e.start_time >= last_rest_end]
                    if post_rest:
                        window_start = post_rest[0].start_time
                else:
                    window_start = on_duty[0].start_time
                if window_start:
                    max_win = self.ADVERSE_MAX_WINDOW if adverse_driving else self.MAX_WINDOW_HOURS
                    window_end = window_start + max_win

        return HOSStatus(
            driving_hours_used=driving.used.total_seconds() / 3600,
            driving_hours_remaining=driving.remaining_hours,
            window_hours_used=window.used.total_seconds() / 3600,
            window_hours_remaining=window.remaining_hours,
            break_hours_driving_since_last=break_check.used.total_seconds() / 3600,
            break_required=break_check.violated,
            cycle_hours_used=cycle.used.total_seconds() / 3600,
            cycle_hours_remaining=cycle.remaining_hours,
            cycle_type=self.cycle_type,
            can_drive=can_drive,
            violations=violations,
            current_duty_status=current_status,
            window_start=window_start,
            window_end=window_end,
            explanations=explanations,
        )

    # ----- Trip Planning / Log Generation -----

    def generate_trip_duty_logs(
        self,
        route_segments: list[RouteSegment],
        historical_days: list[DriverDay],
        start_time: datetime,
        current_cycle_used: float = 0.0,
        avg_speed: float = DEFAULT_AVG_SPEED_MPH,
        adverse_driving: bool = False,
    ) -> TripPlan:
        """
        Forward-simulate a trip and generate HOS-compliant duty status entries.

        Automatically inserts:
          - Pre-trip inspection (15 min on-duty not driving)
          - Pickup stop (1 hour on-duty not driving)
          - 30-minute breaks before 8 cumulative driving hours
          - 10-hour off-duty rest when 11-hour driving or 14-hour window expires
          - Fuel stops every ~1000 miles
          - Dropoff stop (1 hour on-duty not driving)
          - Post-trip inspection (15 min on-duty not driving)
        """
        max_driving = self.ADVERSE_MAX_DRIVING if adverse_driving else self.MAX_DRIVING_HOURS
        max_window = self.ADVERSE_MAX_WINDOW if adverse_driving else self.MAX_WINDOW_HOURS

        entries: list[DutyStatusEntry] = []
        violations: list[HOSViolation] = []
        explanations: list[str] = []

        current = start_time
        cumulative_driving = timedelta(0)
        cumulative_driving_since_break = timedelta(0)
        window_start = start_time
        total_miles_driven = 0.0
        miles_since_fuel = 0.0
        day_number = 1

        # Calculate total route distance
        total_distance = sum(seg.distance_miles for seg in route_segments)

        def add_entry(status, duration, location="", remarks="", lat=0.0, lon=0.0):
            nonlocal current
            entry = DutyStatusEntry(
                status=status,
                start_time=current,
                end_time=current + duration,
                location=location,
                lat=lat,
                lon=lon,
                remarks=remarks,
            )
            entries.append(entry)
            current = current + duration
            return entry

        def take_mandatory_rest(reason=""):
            nonlocal current, cumulative_driving, cumulative_driving_since_break
            nonlocal window_start, day_number

            explanations.append(
                f"Day {day_number}: Rest required - {reason}. "
                f"Driving: {cumulative_driving.total_seconds()/3600:.1f}h, "
                f"Window: {(current - window_start).total_seconds()/3600:.1f}h"
            )

            add_entry(
                DutyStatus.OFF_DUTY,
                timedelta(hours=10),
                remarks=f"10-hour off-duty rest ({reason})",
            )

            cumulative_driving = timedelta(0)
            cumulative_driving_since_break = timedelta(0)
            window_start = current
            day_number += 1

        def take_30_min_break():
            nonlocal cumulative_driving_since_break
            add_entry(
                DutyStatus.OFF_DUTY,
                timedelta(minutes=30),
                remarks="30-minute rest break (§ 395.3(a)(3)(ii))",
            )
            cumulative_driving_since_break = timedelta(0)

        # --- Pre-trip inspection ---
        add_entry(
            DutyStatus.ON_DUTY_NOT_DRIVING,
            timedelta(minutes=15),
            location=route_segments[0].start_location if route_segments else "",
            remarks="Pre-trip inspection",
            lat=route_segments[0].start_lat if route_segments else 0,
            lon=route_segments[0].start_lon if route_segments else 0,
        )

        # --- Pickup (1 hour) ---
        if len(route_segments) > 0:
            add_entry(
                DutyStatus.ON_DUTY_NOT_DRIVING,
                timedelta(hours=1),
                location=route_segments[0].start_location,
                remarks="Pickup / loading",
                lat=route_segments[0].start_lat,
                lon=route_segments[0].start_lon,
            )

        # --- Drive each segment ---
        for seg_idx, segment in enumerate(route_segments):
            miles_to_drive = segment.distance_miles
            drive_hours_needed = miles_to_drive / avg_speed

            MAX_ITERATIONS = 500  # Safety valve against infinite loops
            iteration = 0
            while miles_to_drive > 0.01:  # Tolerance for floating-point
                iteration += 1
                if iteration > MAX_ITERATIONS:
                    break
                hours_left = max(drive_hours_needed, 0)
                if hours_left <= 0.001:
                    break  # Close enough to zero
                window_elapsed = current - window_start

                # Check: do we need a 30-min break?
                time_to_break = (self.BREAK_DRIVING_THRESHOLD - cumulative_driving_since_break)
                if time_to_break <= timedelta(0):
                    take_30_min_break()
                    window_elapsed = current - window_start
                    time_to_break = self.BREAK_DRIVING_THRESHOLD

                # Check: how much can we drive before hitting limits?
                time_to_11hr = max_driving - cumulative_driving
                time_to_14hr = max_window - window_elapsed
                time_to_break_limit = time_to_break

                # Find the most restrictive limit
                drive_limit = min(
                    time_to_11hr,
                    time_to_14hr,
                    time_to_break_limit,
                    timedelta(hours=hours_left),
                )

                if drive_limit <= timedelta(minutes=1):
                    # Cannot drive any more this window; take mandatory rest
                    if time_to_11hr <= timedelta(minutes=1):
                        take_mandatory_rest("11-hour driving limit reached")
                    elif time_to_14hr <= timedelta(minutes=1):
                        take_mandatory_rest("14-hour window expired")
                    else:
                        take_30_min_break()
                    continue

                # Actually drive
                drive_duration = drive_limit
                miles_this_chunk = drive_duration.total_seconds() / 3600 * avg_speed

                # Fuel stop check (every ~1000 miles)
                if miles_since_fuel + miles_this_chunk >= 1000:
                    # Drive to the 1000-mile mark, then fuel
                    miles_to_fuel = 1000 - miles_since_fuel
                    fuel_drive_hours = miles_to_fuel / avg_speed
                    fuel_drive_duration = timedelta(hours=fuel_drive_hours)

                    if fuel_drive_duration > timedelta(0):
                        add_entry(
                            DutyStatus.DRIVING,
                            fuel_drive_duration,
                            remarks=f"Driving",
                            lat=segment.end_lat,
                            lon=segment.end_lon,
                        )
                        cumulative_driving += fuel_drive_duration
                        cumulative_driving_since_break += fuel_drive_duration
                        total_miles_driven += miles_to_fuel
                        miles_to_drive -= miles_to_fuel
                        drive_hours_needed -= fuel_drive_hours

                    # Fuel stop
                    add_entry(
                        DutyStatus.ON_DUTY_NOT_DRIVING,
                        timedelta(minutes=30),
                        remarks="Fuel stop",
                    )
                    miles_since_fuel = 0
                    continue

                add_entry(
                    DutyStatus.DRIVING,
                    drive_duration,
                    location=segment.end_location,
                    remarks="Driving",
                    lat=segment.end_lat,
                    lon=segment.end_lon,
                )

                cumulative_driving += drive_duration
                cumulative_driving_since_break += drive_duration
                miles_driven_chunk = drive_duration.total_seconds() / 3600 * avg_speed
                total_miles_driven += miles_driven_chunk
                miles_since_fuel += miles_driven_chunk
                miles_to_drive -= miles_driven_chunk
                drive_hours_needed -= drive_duration.total_seconds() / 3600

        # --- Dropoff (1 hour) ---
        if route_segments:
            last_seg = route_segments[-1]
            add_entry(
                DutyStatus.ON_DUTY_NOT_DRIVING,
                timedelta(hours=1),
                location=last_seg.end_location,
                remarks="Dropoff / unloading",
                lat=last_seg.end_lat,
                lon=last_seg.end_lon,
            )

        # --- Post-trip inspection ---
        add_entry(
            DutyStatus.ON_DUTY_NOT_DRIVING,
            timedelta(minutes=15),
            remarks="Post-trip inspection",
        )

        # Build daily summaries
        daily_summaries = self._build_daily_summaries(entries)

        return TripPlan(
            entries=entries,
            total_days=day_number,
            total_driving_hours=cumulative_driving.total_seconds() / 3600,
            total_distance_miles=total_distance,
            violations=violations,
            daily_summaries=daily_summaries,
            explanations=explanations,
        )

    def _build_daily_summaries(self, entries: list[DutyStatusEntry]) -> list[dict]:
        """Group entries by calendar day and compute totals."""
        if not entries:
            return []

        days: dict[date, dict] = {}

        for entry in entries:
            day = entry.start_time.date()
            if day not in days:
                days[day] = {
                    "date": day.isoformat(),
                    "driving_hours": 0.0,
                    "on_duty_hours": 0.0,
                    "off_duty_hours": 0.0,
                    "sleeper_hours": 0.0,
                    "entries": [],
                }

            hours = entry.duration_hours
            if entry.status == DutyStatus.DRIVING:
                days[day]["driving_hours"] += hours
            elif entry.status == DutyStatus.ON_DUTY_NOT_DRIVING:
                days[day]["on_duty_hours"] += hours
            elif entry.status == DutyStatus.OFF_DUTY:
                days[day]["off_duty_hours"] += hours
            elif entry.status == DutyStatus.SLEEPER_BERTH:
                days[day]["sleeper_hours"] += hours

            days[day]["entries"].append({
                "status": entry.status.value,
                "start_time": entry.start_time.isoformat(),
                "end_time": entry.end_time.isoformat() if entry.end_time else None,
                "location": entry.location,
                "remarks": entry.remarks,
            })

        return [days[d] for d in sorted(days.keys())]


def compute_rolling_cycle_hours(
    historical_days: list[DriverDay],
    cycle_type: CycleType = CycleType.SEVENTY_EIGHT,
) -> float:
    """
    Convenience function to compute rolling 7/8-day total on-duty hours.

    Per FMCSA (page 10-11): sum on-duty hours from the previous N days.
    The oldest day drops off as each new day is added.
    """
    cycle_days = 8 if cycle_type == CycleType.SEVENTY_EIGHT else 7
    sorted_days = sorted(historical_days, key=lambda d: d.day_date, reverse=True)
    relevant = sorted_days[:cycle_days]
    return sum(d.on_duty_hours for d in relevant)
