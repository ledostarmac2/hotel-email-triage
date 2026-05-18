"""
Comprehensive tests for the PII/sensitive-data redaction module.

All tests are deterministic — no AI calls, no external services.
Covers: Luhn card validation, CVV, expiry, email address, phone,
payment links, confirmation numbers, and combination scenarios.
"""
from __future__ import annotations

import pytest

from outlook_dashboard.redaction import (
    _luhn_valid,
    redact_sensitive_text,
)


# ── Luhn algorithm ────────────────────────────────────────────────────────────

class TestLuhnValidation:
    def test_valid_visa_number(self) -> None:
        assert _luhn_valid("4111111111111111") is True

    def test_valid_mastercard_number(self) -> None:
        assert _luhn_valid("5500005555555559") is True

    def test_valid_amex_number(self) -> None:
        assert _luhn_valid("378282246310005") is True

    def test_invalid_sequential_digits_fail(self) -> None:
        assert _luhn_valid("1234567890123456") is False

    def test_too_short_number_returns_false(self) -> None:
        assert _luhn_valid("123456789012") is False

    def test_all_zeros_passes_luhn_checksum(self) -> None:
        # 16 zeros: every digit doubles to 0, checksum is 0 % 10 == 0 → Luhn-valid.
        # The Luhn algorithm alone cannot reject this; production code relies on
        # real card-issuer BIN ranges to catch obviously fake sequences.
        assert _luhn_valid("0000000000000000") is True

    def test_digits_with_spaces_are_accepted(self) -> None:
        assert _luhn_valid("4111 1111 1111 1111") is True

    def test_digits_with_dashes_are_accepted(self) -> None:
        assert _luhn_valid("4111-1111-1111-1111") is True

    def test_non_digit_chars_ignored(self) -> None:
        assert _luhn_valid("4111 1111 1111 111X") is False  # last digit is bad


# ── Card number redaction ─────────────────────────────────────────────────────

class TestCardRedaction:
    def test_luhn_valid_card_is_redacted(self) -> None:
        text = "Card number: 4111 1111 1111 1111"
        redacted, counts = redact_sensitive_text(text)
        assert "4111 1111 1111 1111" not in redacted
        assert "[REDACTED_CARD]" in redacted
        assert counts["cards"] == 1

    def test_luhn_invalid_sequence_is_not_redacted(self) -> None:
        text = "Reference number: 1234567890123456"
        redacted, counts = redact_sensitive_text(text)
        assert "1234567890123456" in redacted
        assert counts["cards"] == 0

    def test_amex_card_is_redacted(self) -> None:
        text = "AMEX: 378282246310005"
        redacted, counts = redact_sensitive_text(text)
        assert "378282246310005" not in redacted
        assert counts["cards"] == 1

    def test_multiple_cards_all_redacted(self) -> None:
        text = "Primary: 4111 1111 1111 1111. Backup: 5500 0055 5555 5559."
        redacted, counts = redact_sensitive_text(text)
        assert counts["cards"] == 2
        assert "[REDACTED_CARD]" in redacted

    def test_empty_text_returns_zero_counts(self) -> None:
        redacted, counts = redact_sensitive_text("")
        assert redacted == ""
        assert all(v == 0 for v in counts.values())


# ── CVV redaction ─────────────────────────────────────────────────────────────

class TestCVVRedaction:
    def test_cvv_colon_format_is_redacted(self) -> None:
        text = "CVV: 123"
        redacted, counts = redact_sensitive_text(text)
        assert "123" not in redacted
        assert "[REDACTED_CVV]" in redacted
        assert counts["cvv"] == 1

    def test_security_code_phrase_is_redacted(self) -> None:
        text = "security code: 456"
        redacted, counts = redact_sensitive_text(text)
        assert counts["cvv"] == 1

    def test_card_code_phrase_is_redacted(self) -> None:
        text = "card code 789"
        redacted, counts = redact_sensitive_text(text)
        assert counts["cvv"] == 1

    def test_cvc_variant_is_redacted(self) -> None:
        text = "CVC: 321"
        redacted, counts = redact_sensitive_text(text)
        assert counts["cvv"] == 1


# ── Expiry date redaction ─────────────────────────────────────────────────────

class TestExpiryRedaction:
    def test_expires_mm_yy_is_redacted(self) -> None:
        text = "expires 12/29"
        redacted, counts = redact_sensitive_text(text)
        assert "12/29" not in redacted
        assert counts["expiry"] == 1

    def test_expiration_date_long_form_is_redacted(self) -> None:
        text = "expiration date: 03/2027"
        redacted, counts = redact_sensitive_text(text)
        assert counts["expiry"] == 1

    def test_exp_abbreviation_is_redacted(self) -> None:
        text = "exp 06/26"
        redacted, counts = redact_sensitive_text(text)
        assert counts["expiry"] == 1


# ── Email address redaction ───────────────────────────────────────────────────

class TestEmailRedaction:
    def test_plain_email_address_is_redacted(self) -> None:
        text = "Contact: guest@example.com"
        redacted, counts = redact_sensitive_text(text)
        assert "guest@example.com" not in redacted
        assert "[REDACTED_EMAIL]" in redacted
        assert counts["emails"] == 1

    def test_multiple_emails_all_redacted(self) -> None:
        text = "Send to alice@hotel.com and bob@guest.com"
        redacted, counts = redact_sensitive_text(text)
        assert counts["emails"] == 2

    def test_email_in_different_cases_is_redacted(self) -> None:
        text = "Email: GUEST@EXAMPLE.COM"
        redacted, counts = redact_sensitive_text(text)
        assert counts["emails"] == 1


# ── Phone number redaction ────────────────────────────────────────────────────

class TestPhoneRedaction:
    def test_us_phone_with_dashes_is_redacted(self) -> None:
        text = "Call me at 212-555-0100"
        redacted, counts = redact_sensitive_text(text)
        assert "212-555-0100" not in redacted
        assert counts["phones"] == 1

    def test_us_phone_with_dots_is_redacted(self) -> None:
        text = "Phone: 800.555.1234"
        redacted, counts = redact_sensitive_text(text)
        assert counts["phones"] == 1

    def test_us_phone_with_parentheses_is_redacted(self) -> None:
        text = "(212) 555-0100"
        redacted, counts = redact_sensitive_text(text)
        assert counts["phones"] == 1


# ── Payment link redaction ────────────────────────────────────────────────────

class TestPaymentLinkRedaction:
    def test_sertifi_payment_link_is_redacted(self) -> None:
        text = "Sign here: https://sertifi.com/eforms/abc123"
        redacted, counts = redact_sensitive_text(text)
        assert "sertifi.com" not in redacted
        assert counts["payment_links"] == 1

    def test_generic_payment_path_url_is_redacted(self) -> None:
        text = "Pay here: https://secure.example.com/payment/abc"
        redacted, counts = redact_sensitive_text(text)
        assert "secure.example.com" not in redacted
        assert counts["payment_links"] == 1

    def test_checkout_url_is_redacted(self) -> None:
        text = "Complete checkout: https://hotel.com/checkout/order123"
        redacted, counts = redact_sensitive_text(text)
        assert counts["payment_links"] == 1

    def test_invoice_url_is_redacted(self) -> None:
        text = "View invoice: https://billing.example.com/invoice/5678"
        redacted, counts = redact_sensitive_text(text)
        assert counts["payment_links"] == 1

    def test_non_payment_url_is_not_redacted(self) -> None:
        text = "See details at https://www.waldorfastoria.com/reservations"
        redacted, counts = redact_sensitive_text(text)
        assert counts["payment_links"] == 0
        assert "waldorfastoria.com" in redacted


# ── Confirmation number redaction ─────────────────────────────────────────────

class TestConfirmationNumberRedaction:
    def test_confirmation_number_label_is_redacted(self) -> None:
        text = "Confirmation number: RES-88234"
        redacted, counts = redact_sensitive_text(text)
        assert "RES-88234" not in redacted
        assert counts["confirmation_numbers"] == 1

    def test_reservation_id_is_redacted(self) -> None:
        text = "Reservation ID: ABC123456"
        redacted, counts = redact_sensitive_text(text)
        assert counts["confirmation_numbers"] == 1

    def test_folio_number_is_redacted(self) -> None:
        text = "Folio no. FX-129384"
        redacted, counts = redact_sensitive_text(text)
        assert counts["confirmation_numbers"] == 1

    def test_booking_number_is_redacted(self) -> None:
        text = "Booking #BKG-20261101"
        redacted, counts = redact_sensitive_text(text)
        assert counts["confirmation_numbers"] == 1


# ── Combination / real-world scenarios ───────────────────────────────────────

class TestCombinationScenarios:
    def test_full_payment_email_all_pii_redacted(self) -> None:
        text = (
            "Please use card 4111 1111 1111 1111, CVV 123, expires 12/29. "
            "Call me at 212-555-0100 or email guest@example.com. "
            "Payment link: https://secure.example.com/payment/abc. "
            "Confirmation: RES-88234."
        )
        redacted, counts = redact_sensitive_text(text)
        assert counts["cards"] == 1
        assert counts["cvv"] == 1
        assert counts["expiry"] == 1
        assert counts["phones"] == 1
        assert counts["emails"] == 1
        assert counts["payment_links"] == 1
        assert counts["confirmation_numbers"] == 1
        assert "4111" not in redacted
        assert "212-555-0100" not in redacted
        assert "guest@example.com" not in redacted
        assert "RES-88234" not in redacted

    def test_plain_email_body_unchanged(self) -> None:
        text = "Dear team, please confirm the booking for tomorrow night. Thank you."
        redacted, counts = redact_sensitive_text(text)
        assert redacted == text
        assert all(v == 0 for v in counts.values())

    def test_none_values_not_present_in_counts(self) -> None:
        _, counts = redact_sensitive_text("No PII here.")
        for key in ("cards", "cvv", "expiry", "emails", "phones", "payment_links", "confirmation_numbers"):
            assert key in counts
            assert isinstance(counts[key], int)

    def test_redaction_is_idempotent(self) -> None:
        text = "Card: 4111 1111 1111 1111"
        redacted_once, _ = redact_sensitive_text(text)
        redacted_twice, counts = redact_sensitive_text(redacted_once)
        # Second pass should find nothing new
        assert redacted_once == redacted_twice
        assert counts["cards"] == 0
