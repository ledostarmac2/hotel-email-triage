from __future__ import annotations

from datetime import datetime

from outlook_dashboard.hotel_entities import extract, extract_entities


BASE = datetime(2026, 5, 18, 10, 0, 0)


def _entities(text: str, received_at: datetime | None = BASE) -> dict:
    return extract_entities("Subject", text, received_at)


def test_confirmation_number_requires_trigger_word() -> None:
    result = _entities("Call 2125559999 or use order ABC12345.")
    assert result["confirmation_numbers"] == []


def test_confirmation_number_after_confirmation_trigger() -> None:
    result = _entities("Confirmation number ABC12345 for arrival.")
    assert result["confirmation_numbers"] == ["ABC12345"]


def test_confirmation_number_after_booking_hash() -> None:
    result = _entities("Booking # 123456789 is confirmed.")
    assert result["confirmation_numbers"] == ["123456789"]


def test_multiple_confirmation_numbers_preserve_order() -> None:
    result = _entities("Confirmation ABC12345. Reservation 789012.")
    assert result["confirmation_numbers"] == ["ABC12345", "789012"]


def test_billing_amount_extraction() -> None:
    result = _entities("Guest disputes $1,234.56 and asks why $89 was charged.")
    assert result["mentioned_amounts"] == ["$1,234.56", "$89"]


def test_deluxe_king_room_category() -> None:
    assert _entities("Please book a deluxe king.")["room_category"] == "Deluxe King"


def test_deluxe_queen_room_category() -> None:
    assert _entities("Need Deluxe Queen availability.")["room_category"] == "Deluxe Queen"


def test_premier_king_room_category() -> None:
    assert _entities("Upgrade request for Premier King.")["room_category"] == "Premier King"


def test_junior_suite_room_category() -> None:
    assert _entities("The guest requested a junior suite.")["room_category"] == "Junior Suite"


def test_tower_suite_partial_room_category() -> None:
    assert _entities("Can we confirm the tower suite?")["room_category"] == "Tower Suite"


def test_astoria_partial_room_category() -> None:
    assert _entities("Astoria preferred if possible.")["room_category"] == "Astoria Suite"


def test_royal_partial_room_category() -> None:
    assert _entities("Royal setup requested.")["room_category"] == "Royal Suite"


def test_presidential_partial_room_category() -> None:
    assert _entities("Presidential is needed for the VIP.")["room_category"] == "Presidential Suite"


def test_towers_residence_room_category() -> None:
    assert _entities("Towers Residence for long stay.")["room_category"] == "Towers Residence"


def test_no_room_category() -> None:
    assert _entities("Please confirm breakfast hours.")["room_category"] is None


def test_tonight_date() -> None:
    assert _entities("Arriving tonight.")["arrival_date"] == "2026-05-18"


def test_tomorrow_date() -> None:
    assert _entities("Check in tomorrow.")["arrival_date"] == "2026-05-19"


def test_next_thursday_date() -> None:
    assert _entities("Arrival next Thursday.")["arrival_date"] == "2026-05-21"


def test_friday_the_24th_date() -> None:
    assert _entities("Arriving Friday the 24th.")["arrival_date"] == "2026-05-24"


def test_slash_dates_with_arrival_and_departure() -> None:
    result = _entities("Arriving 12/24 departing 12/27.")
    assert result["arrival_date"] == "2026-12-24"
    assert result["departure_date"] == "2026-12-27"
    assert result["nights"] == 3


def test_full_slash_date() -> None:
    assert _entities("Check-in 12/24/2026.")["arrival_date"] == "2026-12-24"


def test_month_name_without_year() -> None:
    assert _entities("Arrival Dec 24.")["arrival_date"] == "2026-12-24"


def test_bare_day_of_month() -> None:
    assert _entities("Arriving the 24th.")["arrival_date"] == "2026-05-24"


def test_nights_computes_departure() -> None:
    result = _entities("Arriving Dec 24 for 3 nights.")
    assert result["departure_date"] == "2026-12-27"
    assert result["nights"] == 3


def test_guest_counts_adults_and_children() -> None:
    result = _entities("Reservation for 2 adults and 1 child.")
    assert result["guest_count_adults"] == 2
    assert result["guest_count_children"] == 1


def test_generic_guest_count_maps_to_adults() -> None:
    result = _entities("Party of 4 guests.")
    assert result["guest_count_adults"] == 4
    assert result["guest_count_children"] is None


def test_rate_code_extraction() -> None:
    assert _entities("Rate code BAR24 applies.")["rate_code"] == "BAR24"


def test_no_dates_returns_none() -> None:
    result = _entities("Please advise when possible.")
    assert result["arrival_date"] is None
    assert result["departure_date"] is None
    assert result["nights"] is None


def test_malformed_dates_do_not_crash() -> None:
    result = _entities("Arriving 99/99/9999 and leaving soon.")
    assert result["arrival_date"] is None


def test_explicit_past_date_is_allowed() -> None:
    assert _entities("Arrival 2025-01-02.")["arrival_date"] == "2025-01-02"


def test_far_future_date_is_allowed() -> None:
    assert _entities("Arrival 2035-08-15.")["arrival_date"] == "2035-08-15"


def test_arrival_window_hours_math() -> None:
    received = datetime(2026, 12, 23, 10, 0, 0)
    result = extract_entities("", "Arrival 12/24/2026.", received)
    assert result["arrival_window_hours"] == 14


def test_arrival_window_requires_received_at() -> None:
    result = extract_entities("", "Arrival 12/24/2026.")
    assert result["arrival_window_hours"] is None


def test_backward_compatible_extract_wrapper() -> None:
    result = extract("Confirmation ABC12345. Deluxe King for 2 adults.")
    assert result["confirmation_numbers"] == ["ABC12345"]
    assert result["guest_count"] == {"adults": 2}
