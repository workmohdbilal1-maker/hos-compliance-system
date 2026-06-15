#!/usr/bin/env python
"""
FMCSA HOS Compliance Verification Report

Runs 10 canonical FMCSA Hours-of-Service scenarios against the HOS engine
and prints a PASS/FAIL compliance report.  No database access is required --
all test data is constructed using the engine's dataclasses directly.

Usage:
    cd backend/
    python verify_hos_compliance.py
"""

import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from datetime import date, timedelta, timezone  # noqa: E402

from django.utils import timezone as tz  # noqa: E402

from apps.hos.engine import (  # noqa: E402
    CycleType,
    DriverDay,
    DutyStatus,
    DutyStatusEntry,
    HOSCalculator,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BASE = tz.now().replace(hour=6, minute=0, second=0, microsecond=0)


def _entry(
    status: DutyStatus,
    start,
    hours: float = 0.0,
    minutes: float = 0.0,
    location: str = "Test Location",
):
    """Build a DutyStatusEntry from a start time and a duration."""
    duration = timedelta(hours=hours, minutes=minutes)
    return DutyStatusEntry(
        status=status,
        start_time=start,
        end_time=start + duration,
        location=location,
    )


def _make_historical_days(hours_per_day, start_date=None):
    """Build DriverDay objects from a list of on-duty hours."""
    if start_date is None:
        start_date = date(2024, 1, 7)
    days = []
    for i, hrs in enumerate(hours_per_day):
        d = start_date + timedelta(days=i)
        days.append(DriverDay(day_date=d, on_duty_hours=hrs, driving_hours=hrs))
    return days


# ---------------------------------------------------------------------------
# Scenario definitions
# ---------------------------------------------------------------------------

results = []  # list of (name, expected_desc, actual_desc, passed)


def record(name, expected_desc, actual_desc, passed):
    results.append((name, expected_desc, actual_desc, passed))


# ---- Scenario 1: Normal 8-hour driving day - no violations ----

def scenario_1():
    calc = HOSCalculator(cycle_type=CycleType.SEVENTY_EIGHT)
    rest_start = BASE - timedelta(hours=10)
    entries = [
        _entry(DutyStatus.OFF_DUTY, rest_start, hours=10),
        _entry(DutyStatus.DRIVING, BASE, hours=8),
    ]
    historical = _make_historical_days([8, 8, 8, 8, 8, 0, 0, 0])
    current_time = BASE + timedelta(hours=8)

    status = calc.calculate_hos_status(
        entries=entries,
        historical_days=historical,
        current_time=current_time,
    )

    passed = (len(status.violations) == 0) and status.can_drive
    record(
        "Normal 8-hour driving day",
        "No violations, can_drive=True",
        f"violations={len(status.violations)}, can_drive={status.can_drive}, "
        f"driving_remaining={status.driving_hours_remaining:.1f}h",
        passed,
    )


# ---- Scenario 2: Maximum 11-hour driving day - at limit, no violation ----

def scenario_2():
    calc = HOSCalculator(cycle_type=CycleType.SEVENTY_EIGHT)
    rest_start = BASE - timedelta(hours=10)
    entries = [
        _entry(DutyStatus.OFF_DUTY, rest_start, hours=10),
        _entry(DutyStatus.DRIVING, BASE, hours=7, minutes=59),
        # 30-min break before hitting 8h cumulative driving
        _entry(DutyStatus.OFF_DUTY, BASE + timedelta(hours=7, minutes=59), minutes=30),
        _entry(DutyStatus.DRIVING, BASE + timedelta(hours=8, minutes=29), hours=3, minutes=1),
    ]
    # Total driving: 7h59m + 3h01m = 11h00m
    historical = _make_historical_days([8, 8, 8, 0, 0, 0, 0, 0])
    current_time = BASE + timedelta(hours=11, minutes=30)

    status = calc.calculate_hos_status(
        entries=entries,
        historical_days=historical,
        current_time=current_time,
    )

    passed = (len(status.violations) == 0) and (status.driving_hours_remaining <= 0.02)
    record(
        "Maximum 11-hour driving day (at limit)",
        "No violations, driving_remaining~0h",
        f"violations={len(status.violations)}, can_drive={status.can_drive}, "
        f"driving_remaining={status.driving_hours_remaining:.2f}h",
        passed,
    )


# ---- Scenario 3: 11-hour + 1 min driving - should trigger violation ----

def scenario_3():
    calc = HOSCalculator(cycle_type=CycleType.SEVENTY_EIGHT)
    rest_start = BASE - timedelta(hours=10)
    entries = [
        _entry(DutyStatus.OFF_DUTY, rest_start, hours=10),
        _entry(DutyStatus.DRIVING, BASE, hours=7, minutes=59),
        _entry(DutyStatus.OFF_DUTY, BASE + timedelta(hours=7, minutes=59), minutes=30),
        _entry(DutyStatus.DRIVING, BASE + timedelta(hours=8, minutes=29), hours=3, minutes=2),
    ]
    # Total driving: 7h59m + 3h02m = 11h01m
    historical = _make_historical_days([8, 8, 8, 0, 0, 0, 0, 0])
    current_time = BASE + timedelta(hours=11, minutes=31)

    status = calc.calculate_hos_status(
        entries=entries,
        historical_days=historical,
        current_time=current_time,
    )

    has_11hr_violation = any(v.rule == "11_hour_driving" for v in status.violations)
    passed = has_11hr_violation and not status.can_drive
    record(
        "11-hour + 1 min driving (violation)",
        "11_hour_driving violation, can_drive=False",
        f"violations={[v.rule for v in status.violations]}, can_drive={status.can_drive}",
        passed,
    )


# ---- Scenario 4: 14-hour window exceeded ----

def scenario_4():
    calc = HOSCalculator(cycle_type=CycleType.SEVENTY_EIGHT)
    # Driver starts at 6:00 AM. 14-hour window ends at 8:00 PM.
    # At 8:01 PM the window is exceeded.
    rest_start = BASE - timedelta(hours=10)
    entries = [
        _entry(DutyStatus.OFF_DUTY, rest_start, hours=10),
        _entry(DutyStatus.ON_DUTY_NOT_DRIVING, BASE, hours=1),  # 6-7 AM
        _entry(DutyStatus.DRIVING, BASE + timedelta(hours=1), hours=5),  # 7 AM-12 PM
        _entry(DutyStatus.OFF_DUTY, BASE + timedelta(hours=6), hours=3),  # 12-3 PM (window still ticks)
        _entry(DutyStatus.DRIVING, BASE + timedelta(hours=9), hours=4),  # 3-7 PM
        _entry(DutyStatus.ON_DUTY_NOT_DRIVING, BASE + timedelta(hours=13), hours=1, minutes=1),  # 7-8:01 PM
    ]
    # current_time at 8:01 PM = 14h01m after 6 AM start
    current_time = BASE + timedelta(hours=14, minutes=1)
    historical = _make_historical_days([8, 8, 8, 0, 0, 0, 0, 0])

    status = calc.calculate_hos_status(
        entries=entries,
        historical_days=historical,
        current_time=current_time,
    )

    has_window_violation = any(v.rule == "14_hour_window" for v in status.violations)
    passed = has_window_violation and not status.can_drive
    record(
        "14-hour window exceeded (drives at 8:01 PM after 6 AM start)",
        "14_hour_window violation, can_drive=False",
        f"violations={[v.rule for v in status.violations]}, can_drive={status.can_drive}, "
        f"window_remaining={status.window_hours_remaining:.2f}h",
        passed,
    )


# ---- Scenario 5: 30-minute break compliance ----

def scenario_5():
    calc = HOSCalculator(cycle_type=CycleType.SEVENTY_EIGHT)
    rest_start = BASE - timedelta(hours=10)
    entries = [
        _entry(DutyStatus.OFF_DUTY, rest_start, hours=10),
        _entry(DutyStatus.DRIVING, BASE, hours=7, minutes=45),
        # 30-min break BEFORE hitting 8h cumulative driving
        _entry(DutyStatus.OFF_DUTY, BASE + timedelta(hours=7, minutes=45), minutes=30),
        _entry(DutyStatus.DRIVING, BASE + timedelta(hours=8, minutes=15), hours=2),
    ]
    current_time = BASE + timedelta(hours=10, minutes=15)
    historical = _make_historical_days([8, 8, 8, 0, 0, 0, 0, 0])

    status = calc.calculate_hos_status(
        entries=entries,
        historical_days=historical,
        current_time=current_time,
    )

    has_break_violation = any(v.rule == "30_min_break" for v in status.violations)
    passed = not has_break_violation and status.can_drive
    record(
        "30-minute break compliance (break before 8h driving)",
        "No 30_min_break violation, can_drive=True",
        f"violations={[v.rule for v in status.violations]}, can_drive={status.can_drive}, "
        f"break_driving_since_last={status.break_hours_driving_since_last:.2f}h",
        passed,
    )


# ---- Scenario 6: 30-minute break violation ----

def scenario_6():
    calc = HOSCalculator(cycle_type=CycleType.SEVENTY_EIGHT)
    rest_start = BASE - timedelta(hours=10)
    entries = [
        _entry(DutyStatus.OFF_DUTY, rest_start, hours=10),
        # Drives 8.5 hours straight without any break
        _entry(DutyStatus.DRIVING, BASE, hours=8, minutes=30),
    ]
    current_time = BASE + timedelta(hours=8, minutes=30)
    historical = _make_historical_days([8, 8, 8, 0, 0, 0, 0, 0])

    status = calc.calculate_hos_status(
        entries=entries,
        historical_days=historical,
        current_time=current_time,
    )

    has_break_violation = any(v.rule == "30_min_break" for v in status.violations)
    passed = has_break_violation and not status.can_drive
    record(
        "30-minute break violation (8.5h driving without break)",
        "30_min_break violation, can_drive=False",
        f"violations={[v.rule for v in status.violations]}, can_drive={status.can_drive}, "
        f"break_driving_since_last={status.break_hours_driving_since_last:.2f}h",
        passed,
    )


# ---- Scenario 7: 70-hour/8-day cycle compliance ----

def scenario_7():
    calc = HOSCalculator(cycle_type=CycleType.SEVENTY_EIGHT)
    rest_start = BASE - timedelta(hours=10)
    entries = [
        _entry(DutyStatus.OFF_DUTY, rest_start, hours=10),
        _entry(DutyStatus.DRIVING, BASE, hours=3),
    ]
    current_time = BASE + timedelta(hours=3)
    # 67 hours across 8 days (varying pattern summing to 67)
    historical = _make_historical_days(
        [10, 9, 8, 8, 9, 7, 8, 8],  # sum = 67
        start_date=date(2024, 1, 7),
    )

    status = calc.calculate_hos_status(
        entries=entries,
        historical_days=historical,
        current_time=current_time,
    )

    has_cycle_violation = any(v.rule == "cycle_limit" for v in status.violations)
    passed = not has_cycle_violation and status.can_drive
    record(
        "70-hour/8-day cycle compliance (67h over 8 days)",
        "No cycle_limit violation, can_drive=True",
        f"violations={[v.rule for v in status.violations]}, can_drive={status.can_drive}, "
        f"cycle_remaining={status.cycle_hours_remaining:.1f}h",
        passed,
    )


# ---- Scenario 8: 70-hour/8-day cycle violation ----

def scenario_8():
    calc = HOSCalculator(cycle_type=CycleType.SEVENTY_EIGHT)
    rest_start = BASE - timedelta(hours=10)
    entries = [
        _entry(DutyStatus.OFF_DUTY, rest_start, hours=10),
        _entry(DutyStatus.DRIVING, BASE, hours=3),
    ]
    current_time = BASE + timedelta(hours=3)
    # 71 hours across 8 days (already exceeds 70)
    # The engine also adds today's on-duty hours (3h driving), so we need
    # the historical days to already push us over 70 when combined with
    # today's 3 hours.  71 + 3 = 74 > 70.
    historical = _make_historical_days(
        [9, 9, 9, 9, 9, 9, 9, 8],  # sum = 71
        start_date=date(2024, 1, 7),
    )

    status = calc.calculate_hos_status(
        entries=entries,
        historical_days=historical,
        current_time=current_time,
    )

    has_cycle_violation = any(v.rule == "cycle_limit" for v in status.violations)
    passed = has_cycle_violation and not status.can_drive
    record(
        "70-hour/8-day cycle violation (71h historical + 3h today)",
        "cycle_limit violation, can_drive=False",
        f"violations={[v.rule for v in status.violations]}, can_drive={status.can_drive}, "
        f"cycle_used={status.cycle_hours_used:.1f}h, cycle_remaining={status.cycle_hours_remaining:.1f}h",
        passed,
    )


# ---- Scenario 9: 34-hour restart resets cycle ----

def scenario_9():
    calc = HOSCalculator(cycle_type=CycleType.SEVENTY_EIGHT)
    # Driver had a 34-hour off-duty period followed by new driving.
    restart_start = BASE - timedelta(hours=34)
    entries = [
        _entry(DutyStatus.OFF_DUTY, restart_start, hours=34),
        _entry(DutyStatus.DRIVING, BASE, hours=4),
    ]

    found, start, end = calc.check_34_hour_restart(entries)

    # After a 34h restart the cycle resets.  Verify the engine detects it.
    passed = found and start == restart_start
    record(
        "34-hour restart resets cycle",
        "restart detected, start matches",
        f"restart_found={found}, restart_start={start}, restart_end={end}",
        passed,
    )


# ---- Scenario 10: Adverse driving conditions ----

def scenario_10():
    calc = HOSCalculator(cycle_type=CycleType.SEVENTY_EIGHT)
    rest_start = BASE - timedelta(hours=10)
    # Build entries with a 30-min break to avoid conflating with the break rule.
    # Drive 7h45m, take 30-min break, then drive 4h15m = 12h total driving.
    # Elapsed wall time: 7h45m + 0h30m + 4h15m = 12h30m on-duty; window at 15h.
    entries = [
        _entry(DutyStatus.OFF_DUTY, rest_start, hours=10),
        _entry(DutyStatus.DRIVING, BASE, hours=7, minutes=45),
        _entry(DutyStatus.OFF_DUTY, BASE + timedelta(hours=7, minutes=45), minutes=30),
        _entry(DutyStatus.DRIVING, BASE + timedelta(hours=8, minutes=15), hours=4, minutes=15),
    ]
    current_time = BASE + timedelta(hours=15)
    historical = _make_historical_days([8, 8, 8, 0, 0, 0, 0, 0])

    # Without adverse driving: 12h driving violates 11h limit; 15h window violates 14h
    status_normal = calc.calculate_hos_status(
        entries=entries,
        historical_days=historical,
        current_time=current_time,
        adverse_driving=False,
    )

    # With adverse driving: limits extend by 2h (driving to 13h, window to 16h)
    status_adverse = calc.calculate_hos_status(
        entries=entries,
        historical_days=historical,
        current_time=current_time,
        adverse_driving=True,
    )

    normal_violated = not status_normal.can_drive and len(status_normal.violations) > 0
    adverse_compliant = status_adverse.can_drive and len(status_adverse.violations) == 0
    passed = normal_violated and adverse_compliant
    record(
        "Adverse driving conditions (extends limits by 2h)",
        "Normal: violations + can_drive=False; Adverse: no violations + can_drive=True",
        f"Normal: violations={[v.rule for v in status_normal.violations]}, can_drive={status_normal.can_drive} | "
        f"Adverse: violations={[v.rule for v in status_adverse.violations]}, can_drive={status_adverse.can_drive}, "
        f"driving_remaining={status_adverse.driving_hours_remaining:.1f}h, "
        f"window_remaining={status_adverse.window_hours_remaining:.1f}h",
        passed,
    )


# ---------------------------------------------------------------------------
# Run all scenarios and print report
# ---------------------------------------------------------------------------

def main():
    print()
    print("=" * 60)
    print("  FMCSA HOS Compliance Verification Report")
    print("=" * 60)
    print()

    scenarios = [
        scenario_1,
        scenario_2,
        scenario_3,
        scenario_4,
        scenario_5,
        scenario_6,
        scenario_7,
        scenario_8,
        scenario_9,
        scenario_10,
    ]

    for i, fn in enumerate(scenarios, 1):
        try:
            fn()
        except Exception as exc:
            record(f"Scenario {i} (ERROR)", "N/A", f"Exception: {exc}", False)

    pass_count = 0
    for i, (name, expected, actual, passed) in enumerate(results, 1):
        status_str = "PASS" if passed else "FAIL"
        print(f"Scenario {i}: {name}")
        print(f"  Expected: {expected}")
        print(f"  Actual:   {actual}")
        print(f"  Result:   {status_str}")
        print()
        if passed:
            pass_count += 1

    total = len(results)
    print("=" * 60)
    if pass_count == total:
        print(f"  Summary: {pass_count}/{total} PASSED")
    else:
        print(f"  Summary: {pass_count}/{total} PASSED, {total - pass_count} FAILED")
    print("=" * 60)
    print()

    sys.exit(0 if pass_count == total else 1)


if __name__ == "__main__":
    main()
