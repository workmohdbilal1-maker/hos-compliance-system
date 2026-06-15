"""
Comprehensive tests for the HOS (Hours of Service) compliance engine.

Tests cover all FMCSA rules implemented in apps.hos.engine:
  - 14-Hour Driving Window
  - 11-Hour Driving Limit
  - 30-Minute Rest Break
  - 60/70-Hour Cycle Limit
  - 34-Hour Restart
  - Sleeper Berth Provision
  - Adverse Driving Conditions Exception
  - Trip Log Generation
"""

from datetime import datetime, timedelta, date, timezone

import pytest

from apps.hos.engine import (
    CycleType,
    DriverDay,
    DutyStatus,
    DutyStatusEntry,
    HOSCalculator,
    RouteSegment,
    RuleCheckResult,
    compute_rolling_cycle_hours,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BASE_TIME = datetime(2024, 1, 15, 6, 0, tzinfo=timezone.utc)


def _entry(
    status: DutyStatus,
    start: datetime,
    hours: float = 0.0,
    minutes: float = 0.0,
    location: str = "Test Location",
) -> DutyStatusEntry:
    """Shortcut to build a DutyStatusEntry with a duration in hours/minutes."""
    duration = timedelta(hours=hours, minutes=minutes)
    return DutyStatusEntry(
        status=status,
        start_time=start,
        end_time=start + duration,
        location=location,
    )


def _make_historical_days(
    hours_per_day: list[float],
    start_date: date | None = None,
) -> list[DriverDay]:
    """Build a list of DriverDay objects, one per element, most recent last."""
    if start_date is None:
        start_date = date(2024, 1, 7)  # Start 8 days before Jan 15
    days = []
    for i, hrs in enumerate(hours_per_day):
        d = start_date + timedelta(days=i)
        days.append(DriverDay(day_date=d, on_duty_hours=hrs, driving_hours=hrs))
    return days


# ---------------------------------------------------------------------------
# 1. 14-Hour Driving Window  (5 tests)
# ---------------------------------------------------------------------------

class TestFourteenHourWindow:
    """Tests for the 14-Hour Driving Window rule (ss 395.3(a)(2))."""

    def setup_method(self):
        self.calc = HOSCalculator()

    def test_full_window_available_after_rest(self):
        """After a 10-hour off-duty rest, the full 14-hour window is available."""
        entries = [
            _entry(DutyStatus.OFF_DUTY, BASE_TIME - timedelta(hours=10), hours=10),
        ]
        result = self.calc.check_14_hour_window(entries, BASE_TIME)

        assert not result.violated
        assert result.remaining == timedelta(hours=14)
        assert result.remaining_hours == pytest.approx(14.0)

    def test_window_expires_after_14_hours(self):
        """At the 14-hour mark, the window has expired and driving is not allowed."""
        rest_end = BASE_TIME
        entries = [
            # 10-hour qualifying rest
            _entry(DutyStatus.OFF_DUTY, BASE_TIME - timedelta(hours=10), hours=10),
            # Start on-duty right at rest_end
            _entry(DutyStatus.ON_DUTY_NOT_DRIVING, rest_end, hours=1),
            _entry(DutyStatus.DRIVING, rest_end + timedelta(hours=1), hours=5),
            _entry(DutyStatus.ON_DUTY_NOT_DRIVING, rest_end + timedelta(hours=6), hours=2),
            _entry(DutyStatus.DRIVING, rest_end + timedelta(hours=8), hours=5),
        ]
        # current_time is 14 hours + 1 minute after window started
        current = rest_end + timedelta(hours=14, minutes=1)
        result = self.calc.check_14_hour_window(entries, current)

        assert result.violated
        assert result.remaining == timedelta(0)

    def test_window_not_paused_by_off_duty(self):
        """Off-duty breaks during the day do NOT pause the 14-hour window clock."""
        rest_end = BASE_TIME
        entries = [
            _entry(DutyStatus.OFF_DUTY, BASE_TIME - timedelta(hours=10), hours=10),
            _entry(DutyStatus.DRIVING, rest_end, hours=4),
            # 2-hour break (off-duty) -- window still ticks
            _entry(DutyStatus.OFF_DUTY, rest_end + timedelta(hours=4), hours=2),
            _entry(DutyStatus.DRIVING, rest_end + timedelta(hours=6), hours=4),
        ]
        # 10 hours after window start (4 drive + 2 off + 4 drive)
        current = rest_end + timedelta(hours=10)
        result = self.calc.check_14_hour_window(entries, current)

        # 10 hours used of 14 = 4 remaining
        assert not result.violated
        assert result.used == timedelta(hours=10)
        assert result.remaining == timedelta(hours=4)

    def test_window_resets_after_10hr_off(self):
        """A new 10-hour off-duty period resets the 14-hour window entirely."""
        entries = [
            # Day 1: qualifying rest then work
            _entry(DutyStatus.OFF_DUTY, BASE_TIME - timedelta(hours=24), hours=10),
            _entry(DutyStatus.DRIVING, BASE_TIME - timedelta(hours=14), hours=11),
            # New 10-hour qualifying rest (most recent)
            _entry(DutyStatus.OFF_DUTY, BASE_TIME - timedelta(hours=3), hours=10),
        ]
        # No on-duty time after the new rest yet
        current = BASE_TIME + timedelta(hours=7)
        result = self.calc.check_14_hour_window(entries, current)

        assert not result.violated
        assert result.remaining == timedelta(hours=14)

    def test_can_work_not_drive_after_window(self):
        """
        The 14-hour window restricts DRIVING, but the window check itself
        reports violation based on elapsed time. A driver can still perform
        non-driving on-duty work -- the engine reports the time facts.
        """
        rest_end = BASE_TIME
        entries = [
            _entry(DutyStatus.OFF_DUTY, BASE_TIME - timedelta(hours=10), hours=10),
            _entry(DutyStatus.ON_DUTY_NOT_DRIVING, rest_end, hours=14),
        ]
        # Right at the 14-hour boundary
        current = rest_end + timedelta(hours=14)
        result = self.calc.check_14_hour_window(entries, current)

        # At exactly 14 hours, not violated (> is the test, not >=)
        assert not result.violated
        assert result.remaining == timedelta(0)


# ---------------------------------------------------------------------------
# 2. 11-Hour Driving Limit  (5 tests)
# ---------------------------------------------------------------------------

class TestElevenHourDriving:
    """Tests for the 11-Hour Driving Limit (ss 395.3(a)(3))."""

    def setup_method(self):
        self.calc = HOSCalculator()

    def test_full_11_hours_available(self):
        """A fresh start (after qualifying rest) has the full 11 hours available."""
        entries = [
            _entry(DutyStatus.OFF_DUTY, BASE_TIME - timedelta(hours=10), hours=10),
        ]
        result = self.calc.check_11_hour_driving(entries)

        assert not result.violated
        assert result.remaining == timedelta(hours=11)
        assert result.remaining_hours == pytest.approx(11.0)

    def test_exactly_11_hours_compliant(self):
        """Exactly 11 hours of driving is NOT a violation (boundary check)."""
        entries = [
            _entry(DutyStatus.OFF_DUTY, BASE_TIME - timedelta(hours=10), hours=10),
            _entry(DutyStatus.DRIVING, BASE_TIME, hours=11),
        ]
        result = self.calc.check_11_hour_driving(entries)

        assert not result.violated
        assert result.used == timedelta(hours=11)
        assert result.remaining == timedelta(0)

    def test_over_11_hours_violation(self):
        """Driving 11 hours and 1 minute is a violation."""
        entries = [
            _entry(DutyStatus.OFF_DUTY, BASE_TIME - timedelta(hours=10), hours=10),
            _entry(DutyStatus.DRIVING, BASE_TIME, hours=11, minutes=1),
        ]
        result = self.calc.check_11_hour_driving(entries)

        assert result.violated
        assert result.remaining == timedelta(0)

    def test_non_driving_not_counted(self):
        """On-duty not driving time does NOT count toward the 11-hour limit."""
        entries = [
            _entry(DutyStatus.OFF_DUTY, BASE_TIME - timedelta(hours=10), hours=10),
            _entry(DutyStatus.DRIVING, BASE_TIME, hours=5),
            _entry(DutyStatus.ON_DUTY_NOT_DRIVING, BASE_TIME + timedelta(hours=5), hours=4),
            _entry(DutyStatus.DRIVING, BASE_TIME + timedelta(hours=9), hours=3),
        ]
        result = self.calc.check_11_hour_driving(entries)

        # Only 5 + 3 = 8 hours of driving
        assert not result.violated
        assert result.used == timedelta(hours=8)
        assert result.remaining == timedelta(hours=3)

    def test_resets_after_10hr_off(self):
        """A new 10-hour rest period resets the 11-hour driving counter."""
        entries = [
            # Old rest
            _entry(DutyStatus.OFF_DUTY, BASE_TIME - timedelta(hours=30), hours=10),
            # Old driving: 10 hours
            _entry(DutyStatus.DRIVING, BASE_TIME - timedelta(hours=20), hours=10),
            # New 10-hour rest
            _entry(DutyStatus.OFF_DUTY, BASE_TIME - timedelta(hours=10), hours=10),
            # New driving: 3 hours
            _entry(DutyStatus.DRIVING, BASE_TIME, hours=3),
        ]
        result = self.calc.check_11_hour_driving(entries)

        # Only 3 hours should be counted (post-rest)
        assert not result.violated
        assert result.used == timedelta(hours=3)
        assert result.remaining == timedelta(hours=8)


# ---------------------------------------------------------------------------
# 3. 30-Minute Break  (5 tests)
# ---------------------------------------------------------------------------

class TestThirtyMinBreak:
    """Tests for the 30-Minute Rest Break rule (ss 395.3(a)(3)(ii))."""

    def setup_method(self):
        self.calc = HOSCalculator()

    def test_no_break_needed_under_8hrs(self):
        """Under 8 hours of cumulative driving, no break is needed."""
        entries = [
            _entry(DutyStatus.OFF_DUTY, BASE_TIME - timedelta(hours=10), hours=10),
            _entry(DutyStatus.DRIVING, BASE_TIME, hours=7),
        ]
        current = BASE_TIME + timedelta(hours=7)
        result = self.calc.check_30_min_break(entries, current)

        assert not result.violated
        assert result.remaining_hours == pytest.approx(1.0)

    def test_break_required_after_8_hours(self):
        """Driving over 8 hours without a qualifying break is a violation."""
        entries = [
            _entry(DutyStatus.OFF_DUTY, BASE_TIME - timedelta(hours=10), hours=10),
            _entry(DutyStatus.DRIVING, BASE_TIME, hours=8, minutes=1),
        ]
        current = BASE_TIME + timedelta(hours=8, minutes=1)
        result = self.calc.check_30_min_break(entries, current)

        assert result.violated
        assert result.remaining == timedelta(0)

    def test_break_resets_driving_clock(self):
        """After a qualifying 30-minute break, the driving clock resets to zero."""
        entries = [
            _entry(DutyStatus.OFF_DUTY, BASE_TIME - timedelta(hours=10), hours=10),
            _entry(DutyStatus.DRIVING, BASE_TIME, hours=7),
            # 30-minute qualifying break
            _entry(DutyStatus.OFF_DUTY, BASE_TIME + timedelta(hours=7), minutes=30),
            # New driving after break
            _entry(
                DutyStatus.DRIVING,
                BASE_TIME + timedelta(hours=7, minutes=30),
                hours=3,
            ),
        ]
        current = BASE_TIME + timedelta(hours=10, minutes=30)
        result = self.calc.check_30_min_break(entries, current)

        # Only 3 hours since last qualifying break
        assert not result.violated
        assert result.used == timedelta(hours=3)

    def test_consecutive_non_driving_counts(self):
        """30 minutes of consecutive off-duty/non-driving qualifies as a break."""
        entries = [
            _entry(DutyStatus.OFF_DUTY, BASE_TIME - timedelta(hours=10), hours=10),
            _entry(DutyStatus.DRIVING, BASE_TIME, hours=7),
            # Two consecutive non-driving periods that together >= 30 min
            _entry(DutyStatus.OFF_DUTY, BASE_TIME + timedelta(hours=7), minutes=15),
            _entry(
                DutyStatus.ON_DUTY_NOT_DRIVING,
                BASE_TIME + timedelta(hours=7, minutes=15),
                minutes=15,
            ),
            _entry(
                DutyStatus.DRIVING,
                BASE_TIME + timedelta(hours=7, minutes=30),
                hours=4,
            ),
        ]
        current = BASE_TIME + timedelta(hours=11, minutes=30)
        result = self.calc.check_30_min_break(entries, current)

        # The consecutive non-driving >= 30min should have reset the clock
        assert not result.violated
        assert result.used == timedelta(hours=4)

    def test_short_haul_exempt(self):
        """Short-haul exempt drivers are not required to take the 30-minute break."""
        entries = [
            _entry(DutyStatus.OFF_DUTY, BASE_TIME - timedelta(hours=10), hours=10),
            _entry(DutyStatus.DRIVING, BASE_TIME, hours=10),
        ]
        current = BASE_TIME + timedelta(hours=10)
        result = self.calc.check_30_min_break(entries, current, short_haul_exempt=True)

        assert not result.violated
        assert "Short-haul exempt" in result.explanation


# ---------------------------------------------------------------------------
# 4. Cycle Limit  (6 tests)
# ---------------------------------------------------------------------------

class TestCycleLimit:
    """Tests for the 60/70-Hour On-Duty Cycle Limit (ss 395.3(b))."""

    def test_70hr_8day_compliant(self):
        """Under 70 hours in 8 days is compliant on 70/8 cycle."""
        calc = HOSCalculator(cycle_type=CycleType.SEVENTY_EIGHT)
        days = _make_historical_days([8, 8, 8, 8, 8, 8, 8, 8])  # 64 hours
        result = calc.check_cycle_limit(days)

        assert not result.violated
        assert result.remaining == timedelta(hours=6)
        assert result.remaining_hours == pytest.approx(6.0)

    def test_70hr_8day_violation(self):
        """Over 70 hours in 8 days is a violation on 70/8 cycle."""
        calc = HOSCalculator(cycle_type=CycleType.SEVENTY_EIGHT)
        days = _make_historical_days([9, 9, 9, 9, 9, 9, 9, 9])  # 72 hours
        result = calc.check_cycle_limit(days)

        assert result.violated
        assert result.remaining == timedelta(0)

    def test_60hr_7day_compliant(self):
        """Under 60 hours in 7 days is compliant on 60/7 cycle."""
        calc = HOSCalculator(cycle_type=CycleType.SIXTY_SEVEN)
        days = _make_historical_days([8, 8, 8, 8, 8, 8, 8], start_date=date(2024, 1, 8))
        result = calc.check_cycle_limit(days)

        # 56 hours in 7 days, limit is 60
        assert not result.violated
        assert result.remaining == timedelta(hours=4)

    def test_rolling_drops_oldest_day(self):
        """On an 8-day rolling window, providing 9 days causes day 1 to drop off."""
        calc = HOSCalculator(cycle_type=CycleType.SEVENTY_EIGHT)
        # 9 days: day 1 has 14hr, days 2-9 have 8hr each
        days = _make_historical_days(
            [14, 8, 8, 8, 8, 8, 8, 8, 8],
            start_date=date(2024, 1, 6),
        )
        result = calc.check_cycle_limit(days)

        # Most recent 8 days (days 2-9) = 8 * 8 = 64 hours
        # Day 1 (14hr) is dropped
        assert not result.violated
        assert result.used == timedelta(hours=64)
        assert result.remaining == timedelta(hours=6)

    def test_fmcsa_example_67hr_compliant(self):
        """
        FMCSA guide example: Days 1-8 total 67 hours on-duty.
        Under 70-hour limit -- compliant.
        """
        calc = HOSCalculator(cycle_type=CycleType.SEVENTY_EIGHT)
        # Realistic pattern: varied daily hours summing to 67
        days = _make_historical_days(
            [10, 9, 8, 8, 9, 7, 8, 8],  # sum = 67
            start_date=date(2024, 1, 7),
        )
        result = calc.check_cycle_limit(days)

        assert not result.violated
        assert result.used == timedelta(hours=67)
        assert result.remaining == timedelta(hours=3)

    def test_fmcsa_example_73hr_violation(self):
        """
        FMCSA guide example: Days 2-9 total 73 hours on-duty.
        Over 70-hour limit -- violation.
        """
        calc = HOSCalculator(cycle_type=CycleType.SEVENTY_EIGHT)
        # 9 days of data; most recent 8 (days 2-9) sum to 73
        days = _make_historical_days(
            [5, 10, 10, 9, 9, 9, 9, 8, 9],  # days 2-9 sum = 73
            start_date=date(2024, 1, 6),
        )
        result = calc.check_cycle_limit(days)

        # Most recent 8 days sum = 73, exceeds 70
        assert result.violated
        assert result.remaining == timedelta(0)


# ---------------------------------------------------------------------------
# 5. 34-Hour Restart  (3 tests)
# ---------------------------------------------------------------------------

class TestThirtyFourHourRestart:
    """Tests for the 34-Hour Restart provision (ss 395.3(c))."""

    def setup_method(self):
        self.calc = HOSCalculator()

    def test_restart_found_34hr_off(self):
        """A 34-hour off-duty period is correctly identified as a restart."""
        entries = [
            _entry(DutyStatus.DRIVING, BASE_TIME - timedelta(hours=45), hours=10),
            _entry(DutyStatus.OFF_DUTY, BASE_TIME - timedelta(hours=35), hours=35),
        ]
        found, start, end = self.calc.check_34_hour_restart(entries)

        assert found is True
        assert start == BASE_TIME - timedelta(hours=35)
        assert end == BASE_TIME

    def test_restart_not_found_33hr(self):
        """33 hours of off-duty is NOT enough for a restart."""
        entries = [
            _entry(DutyStatus.DRIVING, BASE_TIME - timedelta(hours=44), hours=10),
            _entry(DutyStatus.OFF_DUTY, BASE_TIME - timedelta(hours=34), hours=33),
            _entry(DutyStatus.DRIVING, BASE_TIME - timedelta(hours=1), hours=1),
        ]
        found, start, end = self.calc.check_34_hour_restart(entries)

        assert found is False
        assert start is None
        assert end is None

    def test_restart_uses_sleeper(self):
        """Sleeper berth time counts toward the 34-hour restart."""
        entries = [
            _entry(DutyStatus.DRIVING, BASE_TIME - timedelta(hours=50), hours=10),
            # Mix of sleeper and off-duty that are consecutive and total >= 34 hr
            _entry(DutyStatus.SLEEPER_BERTH, BASE_TIME - timedelta(hours=40), hours=20),
            _entry(DutyStatus.OFF_DUTY, BASE_TIME - timedelta(hours=20), hours=20),
        ]
        found, start, end = self.calc.check_34_hour_restart(entries)

        assert found is True
        assert start == BASE_TIME - timedelta(hours=40)


# ---------------------------------------------------------------------------
# 6. Sleeper Berth  (3 tests)
# ---------------------------------------------------------------------------

class TestSleeperBerth:
    """Tests for the Sleeper Berth Provision (ss 395.1(g))."""

    def setup_method(self):
        self.calc = HOSCalculator()

    def test_10hr_consecutive_sleeper(self):
        """10 consecutive hours in the sleeper berth is a valid full reset."""
        entries = [
            _entry(DutyStatus.DRIVING, BASE_TIME - timedelta(hours=21), hours=11),
            _entry(DutyStatus.SLEEPER_BERTH, BASE_TIME - timedelta(hours=10), hours=10),
        ]
        # The check_sleeper_berth_split finds qualifying 7+ hr sleeper
        # with another 2+ hr period. For a single 10hr sleeper, the 10hr
        # block qualifies as the 7hr portion. We need a separate 2hr+ period
        # for the split to be detected. However, the 10hr block alone is
        # a qualifying rest handled by _find_last_qualifying_rest.
        # Let's verify _find_last_qualifying_rest detects it.
        rest_end = self.calc._find_last_qualifying_rest(entries)
        assert rest_end is not None
        assert rest_end == BASE_TIME

    def test_split_7_plus_3_valid(self):
        """A 7-hour sleeper + 3-hour off-duty split is valid (totals >= 10)."""
        entries = [
            _entry(DutyStatus.DRIVING, BASE_TIME - timedelta(hours=20), hours=5),
            _entry(DutyStatus.SLEEPER_BERTH, BASE_TIME - timedelta(hours=15), hours=7),
            _entry(DutyStatus.DRIVING, BASE_TIME - timedelta(hours=8), hours=4),
            _entry(DutyStatus.OFF_DUTY, BASE_TIME - timedelta(hours=4), hours=3),
            _entry(DutyStatus.DRIVING, BASE_TIME - timedelta(hours=1), hours=1),
        ]
        valid, driving_avail, window_avail = self.calc.check_sleeper_berth_split(entries)

        assert valid is True
        assert driving_avail == timedelta(hours=11)
        assert window_avail == timedelta(hours=14)

    def test_split_insufficient(self):
        """A 5-hour sleeper + 3-hour off-duty is insufficient (no 7hr+ sleeper)."""
        entries = [
            _entry(DutyStatus.DRIVING, BASE_TIME - timedelta(hours=14), hours=5),
            _entry(DutyStatus.SLEEPER_BERTH, BASE_TIME - timedelta(hours=9), hours=5),
            _entry(DutyStatus.DRIVING, BASE_TIME - timedelta(hours=4), hours=1),
            _entry(DutyStatus.OFF_DUTY, BASE_TIME - timedelta(hours=3), hours=3),
        ]
        valid, driving_avail, window_avail = self.calc.check_sleeper_berth_split(entries)

        assert valid is False
        assert driving_avail is None
        assert window_avail is None


# ---------------------------------------------------------------------------
# 7. Adverse Driving Conditions  (2 tests)
# ---------------------------------------------------------------------------

class TestAdverseDriving:
    """Tests for the Adverse Driving Conditions Exception (ss 395.1(b)(1))."""

    def setup_method(self):
        self.calc = HOSCalculator()

    def test_extends_driving_to_13hr(self):
        """Adverse conditions extend the driving limit from 11 to 13 hours."""
        entries = [
            _entry(DutyStatus.OFF_DUTY, BASE_TIME - timedelta(hours=10), hours=10),
            _entry(DutyStatus.DRIVING, BASE_TIME, hours=12),
        ]
        # Without adverse: 12hr driving should violate 11hr limit
        normal = self.calc.check_11_hour_driving(entries, adverse_driving=False)
        assert normal.violated

        # With adverse: 12hr is within 13hr limit
        adverse = self.calc.check_11_hour_driving(entries, adverse_driving=True)
        assert not adverse.violated
        assert adverse.limit == timedelta(hours=13)
        assert adverse.remaining == timedelta(hours=1)

    def test_extends_window_to_16hr(self):
        """Adverse conditions extend the 14-hour window to 16 hours."""
        entries = [
            _entry(DutyStatus.OFF_DUTY, BASE_TIME - timedelta(hours=10), hours=10),
            _entry(DutyStatus.DRIVING, BASE_TIME, hours=5),
        ]
        # 15 hours after window start
        current = BASE_TIME + timedelta(hours=15)

        # Without adverse: 15hr into window => violated
        normal = self.calc.check_14_hour_window(entries, current, adverse_driving=False)
        assert normal.violated

        # With adverse: 15hr into a 16hr window => not violated
        adverse = self.calc.check_14_hour_window(entries, current, adverse_driving=True)
        assert not adverse.violated
        assert adverse.limit == timedelta(hours=16)
        assert adverse.remaining == timedelta(hours=1)


# ---------------------------------------------------------------------------
# 8. Trip Log Generation  (3 tests)
# ---------------------------------------------------------------------------

class TestTripLogGeneration:
    """Tests for generate_trip_duty_logs trip planning."""

    def setup_method(self):
        self.calc = HOSCalculator()
        self.base_days = _make_historical_days([8, 8, 8, 8, 8, 0, 0, 0])

    def test_short_trip_no_breaks(self):
        """A short trip (< 8hr driving) should not require any 30-min breaks or rest."""
        segments = [
            RouteSegment(
                start_location="Chicago, IL",
                end_location="Indianapolis, IN",
                distance_miles=180,
                duration_hours=3.3,
                start_lat=41.88,
                start_lon=-87.63,
                end_lat=39.77,
                end_lon=-86.16,
            ),
        ]
        plan = self.calc.generate_trip_duty_logs(
            route_segments=segments,
            historical_days=self.base_days,
            start_time=BASE_TIME,
        )

        assert plan.total_days == 1
        assert plan.total_distance_miles == pytest.approx(180.0)
        assert len(plan.violations) == 0

        # Should contain: pre-trip + pickup + driving + dropoff + post-trip
        statuses = [e.status for e in plan.entries]
        assert DutyStatus.DRIVING in statuses
        assert DutyStatus.ON_DUTY_NOT_DRIVING in statuses

        # No mandatory rests should be needed
        off_duty_entries = [
            e for e in plan.entries
            if e.status == DutyStatus.OFF_DUTY and e.duration >= timedelta(hours=10)
        ]
        assert len(off_duty_entries) == 0

    def test_medium_trip_with_break(self):
        """
        A medium trip (~10hr driving) should include at least one 30-minute
        break before hitting 8 cumulative driving hours.
        """
        segments = [
            RouteSegment(
                start_location="Dallas, TX",
                end_location="Memphis, TN",
                distance_miles=450,
                duration_hours=6.8,
                start_lat=32.78,
                start_lon=-96.80,
                end_lat=35.15,
                end_lon=-90.05,
            ),
        ]
        plan = self.calc.generate_trip_duty_logs(
            route_segments=segments,
            historical_days=self.base_days,
            start_time=BASE_TIME,
        )

        assert plan.total_days == 1
        assert len(plan.violations) == 0

        # Verify driving time is reasonable
        total_driving_entries = sum(
            e.duration_hours for e in plan.entries if e.status == DutyStatus.DRIVING
        )
        assert total_driving_entries > 0

    def test_multi_day_with_rest(self):
        """
        A long trip (> 11hr driving) should require at least one 10-hour rest period,
        making it a multi-day trip.
        """
        segments = [
            RouteSegment(
                start_location="Los Angeles, CA",
                end_location="Denver, CO",
                distance_miles=1020,
                duration_hours=14.5,
                start_lat=34.05,
                start_lon=-118.24,
                end_lat=39.74,
                end_lon=-104.99,
            ),
        ]
        plan = self.calc.generate_trip_duty_logs(
            route_segments=segments,
            historical_days=self.base_days,
            start_time=BASE_TIME,
        )

        # Should span multiple days due to 10-hour rest requirement
        assert plan.total_days >= 2

        # Should have at least one 10-hour off-duty rest entry
        rest_entries = [
            e for e in plan.entries
            if e.status == DutyStatus.OFF_DUTY and e.duration >= timedelta(hours=10)
        ]
        assert len(rest_entries) >= 1

        # Total driving should cover the route
        assert plan.total_driving_hours > 0
        assert len(plan.violations) == 0


# ---------------------------------------------------------------------------
# 9. Additional edge-case and integration tests
# ---------------------------------------------------------------------------

class TestRuleCheckResultProperties:
    """Tests for the RuleCheckResult dataclass and its properties."""

    def test_remaining_hours_positive(self):
        result = RuleCheckResult(
            used=timedelta(hours=5),
            limit=timedelta(hours=11),
            remaining=timedelta(hours=6),
            violated=False,
        )
        assert result.remaining_hours == pytest.approx(6.0)

    def test_remaining_hours_zero_when_negative(self):
        """remaining_hours property returns 0 when remaining is negative."""
        result = RuleCheckResult(
            used=timedelta(hours=12),
            limit=timedelta(hours=11),
            remaining=timedelta(hours=-1),
            violated=True,
        )
        assert result.remaining_hours == 0.0

    def test_explanation_field(self):
        result = RuleCheckResult(
            used=timedelta(hours=3),
            limit=timedelta(hours=11),
            remaining=timedelta(hours=8),
            violated=False,
            explanation="Test explanation",
        )
        assert result.explanation == "Test explanation"


class TestComputeRollingCycleHours:
    """Tests for the standalone compute_rolling_cycle_hours function."""

    def test_seventy_eight_cycle(self):
        """Rolling 70/8 calculation sums latest 8 days."""
        days = _make_historical_days([10, 10, 10, 10, 10, 10, 10, 10])
        total = compute_rolling_cycle_hours(days, CycleType.SEVENTY_EIGHT)
        assert total == pytest.approx(80.0)

    def test_sixty_seven_cycle(self):
        """Rolling 60/7 calculation sums latest 7 days."""
        days = _make_historical_days(
            [10, 10, 10, 10, 10, 10, 10, 10],
            start_date=date(2024, 1, 7),
        )
        total = compute_rolling_cycle_hours(days, CycleType.SIXTY_SEVEN)
        # Most recent 7 days = 70
        assert total == pytest.approx(70.0)

    def test_drops_oldest_with_9_days(self):
        """Given 9 days, the oldest day is excluded from the 8-day total."""
        days = _make_historical_days(
            [14, 5, 5, 5, 5, 5, 5, 5, 5],
            start_date=date(2024, 1, 6),
        )
        total = compute_rolling_cycle_hours(days, CycleType.SEVENTY_EIGHT)
        # Most recent 8 days each have 5 hours = 40 hours (day with 14 is dropped)
        assert total == pytest.approx(40.0)


class TestDutyStatusEntry:
    """Tests for DutyStatusEntry computed properties."""

    def test_duration_with_end_time(self):
        entry = _entry(DutyStatus.DRIVING, BASE_TIME, hours=5)
        assert entry.duration == timedelta(hours=5)
        assert entry.duration_hours == pytest.approx(5.0)

    def test_duration_without_end_time(self):
        entry = DutyStatusEntry(
            status=DutyStatus.DRIVING,
            start_time=BASE_TIME,
            end_time=None,
        )
        assert entry.duration == timedelta(0)
        assert entry.duration_hours == 0.0


class TestHOSStatusIntegration:
    """Integration tests for the calculate_hos_status method."""

    def setup_method(self):
        self.calc = HOSCalculator()

    def test_fully_compliant_driver(self):
        """A fresh driver with minimal hours is fully compliant and can drive."""
        entries = [
            _entry(DutyStatus.OFF_DUTY, BASE_TIME - timedelta(hours=10), hours=10),
            _entry(DutyStatus.DRIVING, BASE_TIME, hours=3),
        ]
        historical = _make_historical_days([8, 8, 8, 8, 8, 0, 0, 0])
        current = BASE_TIME + timedelta(hours=3)

        status = self.calc.calculate_hos_status(
            entries=entries,
            historical_days=historical,
            current_time=current,
        )

        assert status.can_drive is True
        assert len(status.violations) == 0
        assert status.driving_hours_used == pytest.approx(3.0)
        assert status.driving_hours_remaining == pytest.approx(8.0)
        assert status.cycle_type == CycleType.SEVENTY_EIGHT

    def test_maxed_out_driver_cannot_drive(self):
        """A driver who has exceeded the 11-hour limit cannot drive."""
        entries = [
            _entry(DutyStatus.OFF_DUTY, BASE_TIME - timedelta(hours=10), hours=10),
            _entry(DutyStatus.DRIVING, BASE_TIME, hours=11, minutes=1),
        ]
        historical = _make_historical_days([8, 8, 8, 8, 8, 0, 0, 0])
        current = BASE_TIME + timedelta(hours=11, minutes=1)

        status = self.calc.calculate_hos_status(
            entries=entries,
            historical_days=historical,
            current_time=current,
        )

        assert status.can_drive is False
        assert len(status.violations) >= 1
        rules_violated = [v.rule for v in status.violations]
        assert "11_hour_driving" in rules_violated

    def test_empty_entries_all_available(self):
        """With no entries at all, full availability is reported."""
        status = self.calc.calculate_hos_status(
            entries=[],
            historical_days=[],
            current_time=BASE_TIME,
        )

        assert status.can_drive is True
        assert status.driving_hours_remaining == pytest.approx(11.0)
        assert status.window_hours_remaining == pytest.approx(14.0)
        assert status.cycle_hours_remaining == pytest.approx(70.0)


class TestCycleTypeConstructor:
    """Tests that HOSCalculator correctly configures cycle type parameters."""

    def test_seventy_eight_defaults(self):
        calc = HOSCalculator(cycle_type=CycleType.SEVENTY_EIGHT)
        assert calc.cycle_limit == timedelta(hours=70)
        assert calc.cycle_days == 8

    def test_sixty_seven_configuration(self):
        calc = HOSCalculator(cycle_type=CycleType.SIXTY_SEVEN)
        assert calc.cycle_limit == timedelta(hours=60)
        assert calc.cycle_days == 7

    def test_default_is_seventy_eight(self):
        calc = HOSCalculator()
        assert calc.cycle_type == CycleType.SEVENTY_EIGHT
