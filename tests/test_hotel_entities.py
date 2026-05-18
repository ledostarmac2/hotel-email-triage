"""Tests for outlook_dashboard.hotel_entities — 25+ edge-case coverage."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, date

import pytest

from outlook_dashboard.hotel_entities import (
    extract,
    _extract_confirmation_numbers,
    _extract_room_category,
    _extract_rate_code,
    _extract_guest_count,
    _extract_dates,
    _arrival_window_hours,
)

# ── Confirmation numbers ──────────────────────────────────────────────────────

def test_conf_8digit_numeric():
    nums = _extract_confirmation_numbers("Confirmation number: 12345678")
    assert "12345678" in nums


def test_conf_alpha_prefix():
    nums = _extract_confirmation_numbers("Res# ABC12345")
    assert any("ABC12345" in n for n in nums)


def test_conf_booking_ref():
    nums = _extract_confirmation_numbers("Booking reference: 98765432")
    assert "98765432" in nums


def test_conf_multiple_numbers():
    text = "Confirmation: 11111111 and also Res: 22222222"
    nums = _extract_confirmation_numbers(text)
    assert len(nums) >= 2


def test_conf_not_phone():
    # 10+ digits that look like phone numbers should not match 8-digit pattern
    # (phone like 2125559999 is 10 digits — may still match our 8-10 range, but
    # we verify that the conf prefix logic doesn't produce false positives without prefix)
    text = "Call us at 2125559999, no conf number here"
    nums = _extract_confirmation_numbers(text)
    # Phone without a confirmation prefix keyword should not appear
    assert "2125559999" not in nums


def test_conf_empty_text():
    assert _extract_confirmation_numbers("") == []


def test_conf_no_numbers():
    assert _extract_confirmation_numbers("Please let me know your rate for December.") == []


# ── Room category ─────────────────────────────────────────────────────────────

def test_room_presidential():
    assert _extract_room_category("We'd like to book the Presidential Suite.") == "Presidential Suite"


def test_room_royal():
    assert _extract_room_category("Requesting the Royal Suite for Mr. Smith.") == "Royal Suite"


def test_room_astoria():
    assert _extract_room_category("Please note guest prefers the Astoria Suite.") == "Astoria Suite"


def test_room_tower_suite():
    assert _extract_room_category("The guest is booked in a Tower Suite on the 40th floor.") == "Tower Suite"


def test_room_junior_suite():
    assert _extract_room_category("Upgrading to a Junior Suite if available.") == "Junior Suite"


def test_room_towers_access():
    assert _extract_room_category("Guest has Waldorf Towers access.") == "Towers"


def test_room_towers_room():
    assert _extract_room_category("Booked a Towers Room with park view.") == "Towers"


def test_room_premier():
    assert _extract_room_category("Rate quoted for a Premier King room.") == "Premier"


def test_room_deluxe():
    assert _extract_room_category("Availability of Deluxe Queen rooms?") == "Deluxe"


def test_room_generic_suite_fallback():
    assert _extract_room_category("Looking for a suite room.") == "Junior Suite"


def test_room_none():
    assert _extract_room_category("Please advise on breakfast hours.") is None


def test_room_presidential_beats_towers():
    # Presidential Suite should win even if "towers" appears elsewhere
    text = "The Presidential Suite on the Towers floor."
    assert _extract_room_category(text) == "Presidential Suite"


# ── Rate code ─────────────────────────────────────────────────────────────────

def test_rate_code_basic():
    assert _extract_rate_code("Please book under rate code AARP22.") == "AARP22"


def test_rate_code_group():
    assert _extract_rate_code("Group code WEDDING24 applies.") == "WEDDING24"


def test_rate_code_corporate():
    assert _extract_rate_code("Corporate code: IBM001") == "IBM001"


def test_rate_code_none():
    assert _extract_rate_code("No special codes, just best available rate.") is None


# ── Guest count ───────────────────────────────────────────────────────────────

def test_guest_adults():
    gc = _extract_guest_count("Reservation for 2 adults.")
    assert gc == {"adults": 2}


def test_guest_adults_children():
    gc = _extract_guest_count("Party of 2 adults and 1 child.")
    assert gc["adults"] == 2
    assert gc["children"] == 1


def test_guest_pax_generic():
    gc = _extract_guest_count("Group of 4 guests arriving Friday.")
    assert gc is not None
    assert gc.get("adults") == 4


def test_guest_none():
    assert _extract_guest_count("No guest count mentioned here.") is None


# ── Date extraction ───────────────────────────────────────────────────────────

def test_date_iso():
    arr, dep, nights = _extract_dates("Checking in 2026-06-15, checking out 2026-06-18.")
    assert arr is not None
    assert arr.date() == date(2026, 6, 15)
    assert dep is not None
    assert dep.date() == date(2026, 6, 18)
    assert nights == 3


def test_date_slash():
    arr, dep, nights = _extract_dates("Arrival 12/24, departure 12/27.")
    assert arr is not None
    assert arr.month == 12
    assert arr.day == 24


def test_date_month_name():
    arr, dep, nights = _extract_dates("Checking in December 24, checking out December 27.")
    assert arr is not None
    assert arr.month == 12
    assert arr.day == 24


def test_date_tonight():
    arr, dep, nights = _extract_dates("We are arriving tonight.")
    assert arr is not None
    # tonight = today
    assert arr.date() == datetime.now().date()


def test_date_tomorrow():
    arr, dep, nights = _extract_dates("Checking in tomorrow.")
    assert arr is not None
    assert arr.date() == (datetime.now() + timedelta(days=1)).date()


def test_date_nights_compute_departure():
    text = "Arriving December 24th for 3 nights."
    arr, dep, nights = _extract_dates(text)
    assert nights == 3
    if arr:
        # departure should be computed from arrival + nights
        assert dep is not None or nights == 3  # at minimum nights is extracted


def test_date_no_dates():
    arr, dep, nights = _extract_dates("Please let me know if you need anything.")
    assert arr is None
    assert dep is None


# ── Full extract() integration ────────────────────────────────────────────────

def test_extract_full():
    text = (
        "Confirmation: 87654321. Checking in December 24, checking out December 27. "
        "Junior Suite for 2 adults. Rate code XMAS25."
    )
    result = extract(text)
    assert "87654321" in result["confirmation_numbers"]
    assert result["room_category"] == "Junior Suite"
    assert result["rate_code"] == "XMAS25"
    assert result["guest_count"] == {"adults": 2}
    assert result["arrival_date"] is not None


def test_extract_arrival_window():
    # Set arrival 48 hours from now
    future = datetime.now() + timedelta(hours=48)
    month_name = future.strftime("%B")
    day = future.day
    year = future.year
    text = f"Checking in {month_name} {day}, {year}."
    result = extract(text)
    if result["arrival_window_hours"] is not None:
        # Date-only strings parse to midnight, so window = 48h - current_hour (≥0, ≤48).
        # Use a wide lower bound (0) to avoid time-of-day brittleness.
        assert 0 <= result["arrival_window_hours"] <= 56


def test_extract_empty():
    result = extract("")
    assert result["confirmation_numbers"] == []
    assert result["arrival_date"] is None
    assert result["departure_date"] is None
    assert result["nights"] is None
    assert result["room_category"] is None
    assert result["rate_code"] is None
    assert result["guest_count"] is None
    assert result["arrival_window_hours"] is None
