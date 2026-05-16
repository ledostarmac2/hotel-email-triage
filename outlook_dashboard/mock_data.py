from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from .text_utils import utc_now_iso


def build_mock_emails() -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc)
    samples = [
        {
            "graph_message_id": "mock-vip-prearrival-001",
            "subject": "VIP arrival tonight - amenities and early arrival request",
            "sender_name": "Charlotte Carter",
            "sender_email": "charlotte.carter@example.com",
            "received_datetime": now.isoformat(),
            "body_preview": "We are arriving this evening for our anniversary stay and wanted to confirm...",
            "body_text": (
                "Good afternoon,\n\n"
                "My husband and I are arriving this evening for our anniversary stay. "
                "Could you please confirm whether a Central Park view, early check-in, "
                "and a bottle of champagne can be arranged? Our confirmation number is WA74219.\n\n"
                "Warmly,\nCharlotte Carter"
            ),
            "conversation_id": "mock-conversation-vip-001",
            "importance": "high",
            "has_attachments": False,
        },
        {
            "graph_message_id": "mock-billing-dispute-001",
            "subject": "Incorrect charge after checkout",
            "sender_name": "Darren Lee",
            "sender_email": "darren.lee@example.com",
            "received_datetime": (now - timedelta(minutes=32)).isoformat(),
            "body_preview": "I was charged twice for parking and the amount does not match my folio...",
            "body_text": (
                "Hello,\n\n"
                "I checked out yesterday and noticed I was charged twice for parking. "
                "The amount does not match the folio I received at the desk. Please have "
                "someone review this as soon as possible.\n\n"
                "Darren Lee"
            ),
            "conversation_id": "mock-conversation-billing-001",
            "importance": "normal",
            "has_attachments": True,
        },
        {
            "graph_message_id": "mock-accessibility-001",
            "subject": "Accessible room and shower chair request",
            "sender_name": "Priya Shah",
            "sender_email": "priya.shah@example.com",
            "received_datetime": (now - timedelta(hours=1, minutes=15)).isoformat(),
            "body_preview": "Please confirm an accessible king room with roll-in shower...",
            "body_text": (
                "Dear Reservations,\n\n"
                "Please confirm an accessible king room with a roll-in shower and a shower chair "
                "for my stay beginning June 3. I also need the room to be close to the elevator "
                "if available.\n\n"
                "Thank you,\nPriya Shah"
            ),
            "conversation_id": "mock-conversation-accessibility-001",
            "importance": "high",
            "has_attachments": False,
        },
        {
            "graph_message_id": "mock-virtuoso-rate-001",
            "subject": "Virtuoso benefits and flexible rate inquiry",
            "sender_name": "Michael Rivera",
            "sender_email": "michael.rivera@luxe-travel.example",
            "received_datetime": (now - timedelta(hours=3)).isoformat(),
            "body_preview": "Could you confirm Virtuoso amenities and the best available flexible rate...",
            "body_text": (
                "Hi team,\n\n"
                "Could you confirm Virtuoso amenities and the best available flexible rate "
                "for a deluxe queen from July 12 to July 15? The guest prefers breakfast "
                "included and would appreciate any upgrade consideration subject to availability.\n\n"
                "Michael"
            ),
            "conversation_id": "mock-conversation-virtuoso-001",
            "importance": "normal",
            "has_attachments": False,
        },
        {
            "graph_message_id": "mock-complaint-001",
            "subject": "Disappointed with unresolved room issue",
            "sender_name": "Elena Moreau",
            "sender_email": "elena.moreau@example.com",
            "received_datetime": (now - timedelta(hours=4, minutes=10)).isoformat(),
            "body_preview": "I am disappointed that no manager has responded about the noise issue...",
            "body_text": (
                "To whom it may concern,\n\n"
                "I am disappointed that no manager has responded about the noise issue during "
                "our stay. We reported it twice and still had no rest. I expected more from "
                "a Waldorf Astoria hotel.\n\n"
                "Elena Moreau"
            ),
            "conversation_id": "mock-conversation-complaint-001",
            "importance": "high",
            "has_attachments": False,
        },
        {
            "graph_message_id": "mock-internal-rooming-list-001",
            "subject": "Updated rooming list for Sterling Capital group",
            "sender_name": "Amanda Reyes",
            "sender_email": "amanda.reyes@waldorfastoria.com",
            "received_datetime": (now - timedelta(hours=6)).isoformat(),
            "body_preview": "Attached is the updated rooming list for Sterling Capital...",
            "body_text": (
                "Hi Reservations,\n\n"
                "Attached is the updated rooming list for Sterling Capital. Please confirm "
                "that the double queen requests are noted and advise if any names are missing "
                "from the block.\n\n"
                "Amanda"
            ),
            "conversation_id": "mock-conversation-group-001",
            "importance": "normal",
            "has_attachments": True,
        },
    ]
    for sample in samples:
        sample.setdefault("from_name", sample["sender_name"])
        sample.setdefault("from_email", sample["sender_email"])
        sample.setdefault("body_content_type", "text")
        sample.setdefault("body_content", sample["body_text"])
        sample.setdefault("source", "mock")
        sample.setdefault("mailbox_mode", "mock")
        sample.setdefault("created_at", utc_now_iso())
    return samples
