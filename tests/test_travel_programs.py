from __future__ import annotations

from outlook_dashboard.travel_programs import DOMAIN_REGISTRY, detect_program


def test_domain_registry_contains_required_domains() -> None:
    assert DOMAIN_REGISTRY["virtuoso.com"] == "Virtuoso"
    assert DOMAIN_REGISTRY["*.virtuoso.com"] == "Virtuoso"
    assert DOMAIN_REGISTRY["hilton.com"] == "Internal_Hilton"


def test_virtuoso_domain_high_confidence() -> None:
    result = detect_program("advisor@virtuoso.com", "Please confirm.")
    assert result["program"] == "Virtuoso"
    assert result["confidence"] >= 0.9


def test_virtuoso_subdomain_high_confidence() -> None:
    result = detect_program("jane@luxury.virtuoso.com", "Please confirm.")
    assert result["program"] == "Virtuoso"


def test_signature_domain() -> None:
    result = detect_program("agent@signaturetravelnetwork.com", "")
    assert result["program"] == "Signature"


def test_mr_and_mrs_smith_domain() -> None:
    result = detect_program("reservations@mrandmrssmith.com", "")
    assert result["program"] == "Mr_and_Mrs_Smith"


def test_four_seasons_sender_domain() -> None:
    result = detect_program("advisor@fourseasons.com", "")
    assert result["program"] == "FS_Preferred"


def test_hilton_sender_is_internal() -> None:
    result = detect_program("team@hilton.com", "")
    assert result["program"] == "Internal_Hilton"
    assert result["confidence"] >= 0.9


def test_hilton_honors_sender_is_internal() -> None:
    result = detect_program("service@hiltonhonors.com", "")
    assert result["program"] == "Internal_Hilton"


def test_fhr_keyword_fine_hotels() -> None:
    result = detect_program("agent@gmail.com", "Fine Hotels & Resorts booking request.")
    assert result["program"] == "FHR"


def test_fhr_keyword_amex_platinum() -> None:
    result = detect_program("advisor@example.com", "Guest is an Amex Platinum cardholder.")
    assert result["program"] == "FHR"


def test_amex_domain_needs_keyword_confirmation() -> None:
    result = detect_program("agent@americanexpress.com", "General meeting follow-up.")
    assert result["program"] is None
    assert 0.0 < result["confidence"] < 0.6


def test_amex_domain_with_fhr_keyword() -> None:
    result = detect_program("agent@amexgbt.com", "FHR arrival amenities, please.")
    assert result["program"] == "FHR"
    assert result["confidence"] >= 0.78


def test_virtuoso_keyword_strong_signal() -> None:
    result = detect_program("agent@example.com", "Virtuoso advisor amenities requested.")
    assert result["program"] == "Virtuoso"


def test_generic_virtuoso_word_is_not_enough() -> None:
    result = detect_program("traveler@gmail.com", "That was a virtuoso performance.")
    assert result["program"] is None
    assert result["confidence"] == 0.0


def test_stars_keyword() -> None:
    result = detect_program("agent@example.com", "STARS booking for the guest.")
    assert result["program"] == "STARS"


def test_starwood_luxury_keyword() -> None:
    result = detect_program("agent@example.com", "Starwood Luxury benefits apply.")
    assert result["program"] == "STARS"


def test_impresario_keyword() -> None:
    result = detect_program("agent@example.com", "Impresario amenities requested.")
    assert result["program"] == "Impresario"


def test_hyatt_prive_keyword() -> None:
    result = detect_program("agent@example.com", "Hyatt Prive benefits requested.")
    assert result["program"] == "Hyatt_Prive"


def test_advisor_name_from_from_at_pattern() -> None:
    result = detect_program("assistant@agency.com", "Request from Jane Smith at Brownell Travel.")
    assert result["advisor_name"] == "Jane Smith"
    assert result["agency_name"] == "Brownell Travel"


def test_advisor_name_from_signature_lines() -> None:
    signature = "Jane Smith\nAlchemy Travel Advisors\n212-555-0100"
    result = detect_program("jane@alchemy.com", "Virtuoso advisor booking.", signature)
    assert result["advisor_name"] == "Jane Smith"
    assert result["agency_name"] == "Alchemy Travel Advisors"


def test_uncertain_advisor_name_returns_none() -> None:
    result = detect_program("team@example.com", "Regards,\nReservations Team")
    assert result["advisor_name"] is None
    assert result["agency_name"] is None


def test_multi_signal_uses_matching_high_confidence() -> None:
    result = detect_program("advisor@virtuoso.com", "Virtuoso advisor booking.")
    assert result["program"] == "Virtuoso"
    assert result["confidence"] > 0.92
