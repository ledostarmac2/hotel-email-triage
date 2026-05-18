from __future__ import annotations

from datetime import datetime

import pytest

from outlook_dashboard.hotel_entities import extract_entities
from outlook_dashboard.training_pipeline import _build_example
from outlook_dashboard.travel_programs import detect_program
from outlook_dashboard.urgency_engine import compute_urgency


BASE = datetime(2026, 5, 18, 10, 0, 0)


@pytest.mark.parametrize(
    ("language", "body", "confirmation"),
    [
        (
            "Spanish",
            "Confirmación ES12345. Llegada 24 diciembre 2026 salida 27 diciembre 2026. "
            "2 adultos y 1 niño. Suite presidencial.",
            "ES12345",
        ),
        (
            "French",
            "Réservation FR12345. Arrivée 24 décembre 2026 départ 27 décembre 2026. "
            "2 adultes et 1 enfant. Suite présidentielle.",
            "FR12345",
        ),
        (
            "Portuguese",
            "Reserva PT12345. Chegada 24 dezembro 2026 saída 27 dezembro 2026. "
            "2 adultos e 1 criança. Suite presidencial.",
            "PT12345",
        ),
        (
            "Italian",
            "Conferma IT12345. Arrivo 24 dicembre 2026 partenza 27 dicembre 2026. "
            "2 adulti e 1 bambini. Suite presidenziale.",
            "IT12345",
        ),
        (
            "German",
            "Bestätigung DE12345. Ankunft 24. Dezember 2026 Abreise 27. Dezember 2026. "
            "2 Erwachsene und 1 Kinder. Präsidentensuite.",
            "DE12345",
        ),
    ],
)
def test_multilingual_reservation_entity_suite(language: str, body: str, confirmation: str) -> None:
    entities = extract_entities(f"{language} reservation", body, BASE)

    assert entities["confirmation_numbers"] == [confirmation]
    assert entities["arrival_date"] == "2026-12-24"
    assert entities["departure_date"] == "2026-12-27"
    assert entities["nights"] == 3
    assert entities["room_category"] == "Presidential Suite"
    assert entities["guest_count_adults"] == 2
    assert entities["guest_count_children"] == 1
    assert entities["arrival_window_hours"] == 5270


@pytest.mark.parametrize(
    ("subject", "body", "expected_level", "reason_part"),
    [
        ("Factura incorrecta", "Solicito reembolso por cobro duplicado, por favor.", 4, "billing"),
        ("Réclamation", "Plainte: la chambre était inacceptable.", 4, "complaint"),
        ("Cancellazione futura", "Per favore cancellare la prenotazione.", 2, "cancellation"),
        ("Danke", "Danke, bestätigt und alles gut.", 1, "thank-you"),
        ("Barrierefrei", "Bitte ein barrierefrei Zimmer wegen Allergie bestätigen.", 4, "risk"),
    ],
)
def test_multilingual_urgency_suite(subject: str, body: str, expected_level: int, reason_part: str) -> None:
    hours = 24 * 30 if "Cancellazione" in subject else None
    level, reason = compute_urgency(
        subject,
        body,
        {"arrival_window_hours": hours},
        {"program": None, "confidence": 0.0},
    )

    assert level == expected_level
    assert reason_part in reason.lower()


def test_multilingual_vip_arrival_flow_reaches_l5() -> None:
    body = (
        "Virtuoso advisor booking. Confirmación VIP7777. Llegada 20 mayo 2026 salida 22 mayo 2026. "
        "Por favor confirmar amenidad para Suite presidencial."
    )
    entities = extract_entities("Llegada VIP", body, BASE)
    program = detect_program("advisor@virtuoso.com", body)

    level, reason = compute_urgency("Llegada VIP", body, entities, program)

    assert entities["arrival_window_hours"] == 38
    assert program["program"] == "Virtuoso"
    assert level == 5
    assert reason.startswith("L5")


def test_multilingual_training_example_keeps_sanitized_payload_only() -> None:
    row = {
        "sender_email": "maria.garcia@example.es",
        "subject": "Solicitud de pago confirmación ES12345",
        "body_text": (
            "Hola, soy María García. Por favor use la tarjeta 4111111111111111 exp 12/29 "
            "y llámeme al 212-555-0100 para la confirmación ES12345."
        ),
        "analysis_engine": "heuristic",
        "recommended_department_owner": "Reservations",
        "category": "Billing dispute",
        "priority_level": "High",
        "status": "Completed",
        "guest_sentiment": "Concerned",
        "missing_information": False,
        "reply_required": True,
        "escalation_required": False,
    }

    example = _build_example(row, row, "heuristic")

    serialized = str(example)
    assert "4111111111111111" not in serialized
    assert "212-555-0100" not in serialized
    assert "maria.garcia@example.es" not in serialized
    assert "ES12345" not in example["body_redacted"]
    assert example["sender_domain"] == "example.es"
    assert example["label_urgency"] == 4
    assert example["label_owner"] == "Reservations"
    assert example["label_category"] == "Billing dispute"
