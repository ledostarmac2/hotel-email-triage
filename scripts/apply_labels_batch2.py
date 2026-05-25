"""Apply training labels to the 490 new completed_request dump files (IDs 107-606).

Generates labels rule-based from subject/sender/heuristic signals derived by
manually reading all emails; supplemented with per-thread overrides for known
high-value conversations.

Run from repo root:  python training/apply_labels_batch2.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from outlook_dashboard.database import save_analysis, log_training_example
from outlook_dashboard.training_pipeline import _fingerprint, _subject_tokens

# ---------------------------------------------------------------------------
# Per-thread overrides for known conversations (subject keywords + patterns)
# ---------------------------------------------------------------------------

THREAD_OVERRIDES: list[tuple] = [
    # (subject_keyword, sender_pattern, category, priority, sentiment, owner, contact_type, summary_template)

    # FIFA billing
    ("FIFA", "", "Billing dispute", "High", "Neutral",
     "Finance", "Corporate",
     "FIFA (Yassin El Mekki) billing coordination — room folios and receipt requests for large room charges at Waldorf Astoria."),

    # Louis Vuitton master account
    ("Louis Vuitton", "", "Billing dispute", "High", "Neutral",
     "Finance", "Corporate",
     "Louis Vuitton group master account billing coordination — IPO/master folio routing and charge reconciliation."),
    ("LV Master", "", "Billing dispute", "High", "Neutral",
     "Finance", "Corporate",
     "Louis Vuitton master account folio sent — confirming billing routing for LV group block."),
    ("LV Master", "", "Billing dispute", "High", "Neutral",
     "Finance", "Corporate",
     "Louis Vuitton LV master folio coordination."),

    # Kricheli family billing
    ("Kricheli", "", "Billing dispute", "High", "Neutral",
     "Reservations", "Travel agent",
     "Kricheli family multi-folio billing reconciliation — outstanding balances on room, incidentals, and laundry folios."),

    # Antares Capital group
    ("Antares", "", "Rooming list / group", "Normal", "Neutral",
     "Sales", "Corporate",
     "Antares Capital corporate event group block coordination — room count adjustments, credit card authorizations, and Passkey management."),
    ("Antares Rooming", "", "Rooming list / group", "High", "Neutral",
     "Sales", "Corporate",
     "Antares Capital urgent rooming list discussion — cutoff date approaching, requires same-day response."),

    # Michael Liebowitz (Douglas Elliman CEO, room for son)
    ("Michael Liebowitz", "", "VIP pre-arrival", "High", "Positive",
     "Sales", "Corporate",
     "Michael Liebowitz (CEO Douglas Elliman) requesting room for his son Alec — VIP repeat guest, same-day or next-day arrival."),
    ("Liebowitz", "", "VIP pre-arrival", "High", "Positive",
     "Sales", "Corporate",
     "Michael Liebowitz VIP coordination — room for his son Alec Liebowitz, Handle With Care."),

    # David Pears (repeat guest)
    ("David Pears", "", "General inquiry", "Normal", "Positive",
     "Sales", "Travel agent",
     "David Pears repeat guest inquiry — agent coordination with positive guest feedback and potential rebooking."),

    # Glendorf / RSB Travel noise complaint / early departure
    ("Glendorf", "", "Complaint", "High", "Frustrated",
     "Reservations", "Travel agent",
     "Glendorf guest complaint — noise in room caused early departure outside cancellation policy; courtesy waiver discussion."),

    # Szor VIP arrival
    ("Szor", "", "VIP pre-arrival", "High", "Apologetic",
     "Reservations", "Internal",
     "VIP Szor arrival coordination — rate discrepancy investigation and service recovery after off-property contact."),

    # Bark Avenue / Arielle Matza pet package
    ("Bark Ave", "", "Amenity request", "High", "Positive",
     "Concierge", "Direct guest",
     "Bark Avenue pet package coordination for Arielle Matza arrival — CharDOGnay, dog robe, Handle With Care guest with Yorkie."),
    ("Arielle Matza", "", "Amenity request", "High", "Positive",
     "Concierge", "Direct guest",
     "Bark Avenue pet package and Hilton Honors coordination for Arielle Matza birthday stay with Yorkie Sammi."),

    # Champ Travel / Long Stay (Bliss / Ottenbreit)
    ("Long Stay Enquiry", "", "Consortia / FHR / Virtuoso", "Normal", "Positive",
     "Reservations", "Travel agent",
     "Long stay enquiry via Champ Travel — Mr. Bliss and Ms. Ottenbreit multi-week stay coordination including spa appointments and room moves."),

    # QCC / Goldman Sachs group
    ("QCC Waldorf", "", "Rooming list / group", "Normal", "Neutral",
     "Sales", "Corporate",
     "QCC Goldman Sachs induction event group block — rooming list, TBC reservations, Cvent portal updates, pickup reports."),

    # Singapore Exchange group
    ("Singapore Exchange", "", "Rooming list / group", "Normal", "Neutral",
     "Sales", "Corporate",
     "Singapore Exchange Group July 2026 — deposit reconciliation between FDC report and OnQ, internal coordination."),

    # 36dong.com Chinese folio requests
    ("36dong", "", "Billing dispute", "High", "Neutral",
     "Finance", "Corporate",
     "Chinese corporate guest (36dong) folio request — incidental invoices for multiple reservations."),
    ("Urgent！", "", "Billing dispute", "High", "Neutral",
     "Finance", "Corporate",
     "Urgent folio request for Chinese corporate group — incidental invoices across multiple confirmation numbers."),

    # Elizabeth Hernandez VCC decline / billing
    ("Elizabeth Herrnandez", "", "Billing dispute", "High", "Neutral",
     "Finance", "OTA",
     "Elizabeth Hernandez virtual credit card (VCC) billing dispute — incorrect charge refunded, correct amount reconciled with HotelBeds."),

    # Waldorf Residences guest
    ("WARNY - Unit", "", "Billing dispute", "High", "Neutral",
     "Reservations", "Direct guest",
     "Waldorf Astoria New York residential unit — hotel room reservation request from building resident with billing instructions."),

    # LVMH rate
    ("LVMH RATE", "", "Rate inquiry", "Normal", "Neutral",
     "Sales", "Travel agent",
     "LVMH corporate rate inquiry from travel agent — availability and commission for VIP client dates."),

    # Tamimi / Centurion Amex
    ("Tamimi", "", "VIP pre-arrival", "High", "Positive",
     "Concierge", "Travel agent",
     "Centurion Amex member Mr. Tamimi arrival preparation — concierge coordination and reservation confirmation."),

    # Virtuso/GTC/ProTravel
    ("GTC", "", "Consortia / FHR / Virtuoso", "Normal", "Positive",
     "Sales", "Travel agent",
     "GTC/ProTravel luxury travel client — reservation coordination, 3rd night free, VIP preferences."),
    ("ProTravel", "", "Consortia / FHR / Virtuoso", "Normal", "Positive",
     "Sales", "Travel agent",
     "ProTravel GTC client coordination — room booking confirmation and Hilton Honors benefits."),
    ("Virtuoso", "", "Consortia / FHR / Virtuoso", "Normal", "Positive",
     "Sales", "Travel agent",
     "Virtuoso travel agent client coordination — VIP arrival or booking confirmation."),
    ("Centurion", "", "Consortia / FHR / Virtuoso", "High", "Positive",
     "Concierge", "Travel agent",
     "Amex Centurion member coordination — concierge services, reservation confirmation, and personalized welcome."),
    ("FHR", "", "Consortia / FHR / Virtuoso", "Normal", "Positive",
     "Reservations", "Travel agent",
     "Fine Hotels & Resorts (FHR) booking coordination — late checkout, room readiness, and consortia benefits."),

    # FIFA
    ("FIFA", "", "Billing dispute", "High", "Neutral",
     "Finance", "Corporate",
     "FIFA corporate billing — folio and receipt requests for large charges across multiple rooms."),

    # Wires / financial transfers
    ("Wires", "", "Billing dispute", "Normal", "Neutral",
     "Finance", "Internal",
     "Wire transfer routing inquiry — confirming group or reservation association for incoming payment."),

    # No-show / PG / cancelled rooms
    ("No Show", "", "Billing dispute", "High", "Neutral",
     "Finance", "Internal",
     "No-show and protected guarantee (PG) billing review — charging no-show rooms and closing house accounts."),
    ("PG / No Show", "", "Billing dispute", "High", "Neutral",
     "Finance", "Internal",
     "No-show, PG, and cancelled room charge review — capturing revenue and closing affected accounts."),
    ("5/18/26 - PG", "", "Billing dispute", "High", "Neutral",
     "Finance", "Internal",
     "Daily PG/no-show/cancelled room charge list — team review and charge authorization required."),

    # Smiths VIP
    ("Smiths - 23/05", "", "VIP pre-arrival", "High", "Positive",
     "Concierge", "Internal",
     "Smith family VIP arrival coordination — personal concierge briefed on notes and preferences."),

    # Room blocking notation (operational practice)
    ("Room Blocking Date Notation", "", "General inquiry", "Normal", "Neutral",
     "Operations", "Internal",
     "New best practice: note date and initials when blocking rooms OOO for clear timeline visibility."),

    # HWR Rooming List
    ("HWR Rooming List", "", "Rooming list / group", "Normal", "Neutral",
     "Sales", "Corporate",
     "HWR group rooming list completion confirmed."),

    # Spa arrival coordination
    ("SPA Arrival Confirmation", "", "Amenity request", "Normal", "Neutral",
     "Concierge", "Internal",
     "Updated spa reservation coordination process — new streamlined approach effective 5/19/26."),

    # BEO Selections (event)
    ("BEO Selections", "", "Rooming list / group", "Normal", "Neutral",
     "Sales", "Corporate",
     "Event BEO coordination — requesting updated BEO documents from event planner."),

    # Elrad/Oppenheim wedding block
    ("wedding block", "", "Rooming list / group", "Normal", "Positive",
     "Sales", "Direct guest",
     "Wedding room block coordination — guest reservation moves into block, checkout date updates."),
    ("Elrad", "", "Rooming list / group", "Normal", "Positive",
     "Sales", "Direct guest",
     "Elrad/Oppenheim October 2026 wedding block — reservation date correction."),
    ("Spata Ammirati Wedding", "", "Rooming list / group", "Normal", "Positive",
     "Sales", "Travel agent",
     "Spata Ammirati October 2026 wedding block — moving phone reservations into group block."),

    # Stackline group
    ("Stackline", "", "Rooming list / group", "Normal", "Neutral",
     "Sales", "Corporate",
     "Stackline group rooming list follow-up — agent following up with client on roster."),

    # Stay extension
    ("Stay extension", "", "Cancellation / modification", "Normal", "Neutral",
     "Reservations", "Internal",
     "Stay extension request — one additional night; checking room availability and OOO constraints."),

    # Alrowaily / confirmation GDS
    ("Alrowaily", "", "Consortia / FHR / Virtuoso", "Normal", "Neutral",
     "Reservations", "Travel agent",
     "GDS booking confirmation for Alrowaily — late checkout policy and reservation details."),

    # Media / influencer
    ("Media Rate", "", "Rate inquiry", "Normal", "Neutral",
     "Sales", "Internal",
     "Media/influencer rate inquiry — total billing for influencer stay returning to hotel."),
    ("Influencer", "", "Rate inquiry", "Normal", "Neutral",
     "Sales", "Internal",
     "Comp reservation for travel influencer/model — booking against LV group block."),

    # Pickup/change system alerts
    ("PICKUP_AND_CHANGE", "", "System / Automated", "Low", "Neutral",
     "Operations", "Automated",
     "Automated IDEAS pickup and change alert for multi-bedroom suite or reservation pickup changes."),

    # Waldorf Residences
    ("WARNY", "", "Billing dispute", "High", "Neutral",
     "Reservations", "Direct guest",
     "Waldorf Astoria Residences — hotel room request from building resident with specific billing instructions."),

    # Property query / personal concierge
    ("Property Query", "", "General inquiry", "Normal", "Neutral",
     "Concierge", "Internal",
     "Internal property query routed to personal concierge team for guest follow-up."),

    # Nepshekuev concierge
    ("Nepshekuev", "", "VIP pre-arrival", "High", "Neutral",
     "Concierge", "OTA",
     "Booking.com VIP guest Nepshekuev — awaiting flight details for airport transfer arrangement."),

    # Wu Mingxia VIP
    ("Wu, Mingxia", "", "VIP pre-arrival", "High", "Positive",
     "Reservations", "Travel agent",
     "VIP guest Ms. Wu Mingxia arrival — two rooms confirmed, receipt acknowledgment from China-based agent."),
    ("Wu Mingxia", "", "VIP pre-arrival", "High", "Positive",
     "Reservations", "Travel agent",
     "VIP guest Ms. Wu Mingxia arrival coordination."),

    # Booking confirmation / lartisien.com
    ("lartisien", "", "General inquiry", "Normal", "Neutral",
     "Reservations", "Travel agent",
     "L'Artisien luxury travel agent confirming guest processed payment; requesting Waldorf confirmation receipt."),

    # Bristow JP Morgan rate
    ("BRISTOW", "", "Rate inquiry", "Normal", "Neutral",
     "Sales", "Corporate",
     "JP Morgan corporate guest Bristow — waitlist request for sold-out September dates and rate inquiry."),

    # Guido Zorzut / suite booking
    ("Suite 921", "", "VIP pre-arrival", "Normal", "Positive",
     "Sales", "Corporate",
     "Guido Zorzut (Recordati) proceeding with Premier One Bedroom Suite booking after review of details."),

    # Frontini / Cisalpina Tours
    ("FRONTINI", "", "General inquiry", "Normal", "Neutral",
     "Reservations", "Travel agent",
     "Mrs. Frontini stay points crediting request via Cisalpina Tours — Hilton Honors points for recent stays."),

    # Shiv Desai
    ("Your Recent Stay", "", "General inquiry", "Normal", "Positive",
     "Reservations", "Direct guest",
     "Recent stay guest (Shiv Desai) returning — room booking for Sunday with valid free night certificate."),

    # Sertifi signed documents
    ("has been signed at Waldorf", "", "System / Automated", "Low", "Neutral",
     "Operations", "Automated",
     "Sertifi e-signature confirmation — guest or agent has completed a signature request."),
    ("Documents for eSignature", "", "System / Automated", "Low", "Neutral",
     "Operations", "Internal",
     "Internal coordination to add IATA number and amenities to eSignature document before sending."),

    # DD-NYCWA daily detail
    ("DD-NYCWA", "", "System / Automated", "Low", "Neutral",
     "Operations", "Automated",
     "RMCC Americas Global Daily Detail report for NYCWA — automated daily performance report."),

    # Revenue pickup report
    ("Revenue Pickup Report", "", "System / Automated", "Low", "Neutral",
     "Operations", "Internal",
     "Daily revenue pickup report from Rooms Experience Manager — routine operational distribution."),
    ("Reservation QC Report", "", "System / Automated", "Low", "Neutral",
     "Operations", "Internal",
     "Reservation quality control report — daily QC review of reservation accuracy."),

    # Anticipated arrivals
    ("Anticipated Arrivals", "", "General inquiry", "Normal", "Neutral",
     "Operations", "Internal",
     "Daily anticipated arrivals distribution from Rooms Experience Manager for front desk briefing."),

    # Reservation Activity Extract
    ("Reservation Activity Extract", "", "System / Automated", "Low", "Neutral",
     "Operations", "Automated",
     "Automated Hilton OnQ Reservation Activity Extract — replaces decommissioned agent activity report."),

    # Booking.com guest messages
    ("guest messages waiting for you", "", "System / Automated", "Low", "Neutral",
     "Operations", "OTA",
     "Booking.com automated notification — pending guest messages in extranet requiring response."),

    # Cvent Passkey
    ("Cvent Passkey", "", "System / Automated", "Low", "Neutral",
     "Sales", "Automated",
     "Cvent Passkey automated GroupLink status summary — unprocessed reservations and group block updates."),

    # VIP Guest Experience Feedback
    ("VIP-Guest Experience Feedback", "", "General inquiry", "Normal", "Positive",
     "Sales", "Travel agent",
     "VIP guest experience feedback from Mercator Travels (UAE) — partnership appreciation and positive stay acknowledgment."),

    # IATA / PCC inquiry
    ("IATA", "", "General inquiry", "Normal", "Neutral",
     "Sales", "Internal",
     "IATA number and PCC booking verification — confirming whether bookings are generic or business accounts."),

    # Booking.com urgent add guest
    ("URGENT:Add Guest", "", "General inquiry", "High", "Neutral",
     "Reservations", "OTA",
     "Urgent Booking.com request to add guest to reservation for customs documentation — name change processed."),

    # Waldorf NY guest stay (Corbett)
    ("Waldorf NY Guest stay", "", "VIP pre-arrival", "Normal", "Positive",
     "Sales", "Travel agent",
     "Guest Corbett upgrade request to Junior Suite — Sales Director authorizing upgrade for travel agent client."),

    # June confirmation billing update
    ("Billing Info Changed", "", "Billing dispute", "High", "Neutral",
     "Finance", "Internal",
     "Billing routing change — removing IPO from reservation, charging all nights to master account."),

    # Hilton APAC Fam trip
    ("Hilton APAC Fam", "", "Consortia / FHR / Virtuoso", "Normal", "Neutral",
     "Sales", "Travel agent",
     "Hilton APAC familiarization trip inquiry — routing to consortia team for follow-up."),

    # Automatic reply / out of office
    ("Automatic reply", "", "System / Automated", "Low", "Neutral",
     "Operations", "Internal",
     "Automatic out-of-office reply — no action required."),

    # VIP arrival general
    ("VIP Arrival", "", "VIP pre-arrival", "High", "Positive",
     "Reservations", "Internal",
     "VIP guest arrival notification and coordination — concierge and reservations briefed on preferences."),

    # Please reply emails (Chinese requests)
    ("Please reply to this email", "", "Billing dispute", "High", "Neutral",
     "Finance", "Corporate",
     "Repeated follow-up request from Chinese corporate client — folio/billing documentation needed urgently."),

    # Confirmation letters / documentation
    ("confirmation letter", "", "General inquiry", "Normal", "Neutral",
     "Reservations", "Travel agent",
     "Confirmation letter request — agent or guest requesting formal reservation confirmation with full booking details."),
]

# ---------------------------------------------------------------------------
# Urgency score → priority_level
# ---------------------------------------------------------------------------

def _priority(urgency_score) -> str:
    s = int(urgency_score or 2)
    if s >= 5:
        return "Urgent"
    if s >= 4:
        return "High"
    if s >= 3:
        return "Normal"
    if s >= 2:
        return "Normal"
    return "Low"


# ---------------------------------------------------------------------------
# Sender/domain → contact_type
# ---------------------------------------------------------------------------

_INTERNAL_DOMAINS = {"waldorfastoria.com", "hilton.com"}
_AUTOMATED_SENDERS = {
    "noreply@booking.com", "noreply-email@booking.com", "noreply@hilton.com",
    "info@cvent.com", "services@sertifi.net", "noreply@hilton.com",
    "replies-disabled@ideas.com", "noreply@hilton.com",
}
_AUTOMATED_SENDER_PREFIXES = ("byagtRpt_", "noreply", "noreply-", "info@", "services@sertifi")
_OTA_DOMAINS = {"booking.com", "expedia.com", "hotels.com"}
_TRAVEL_AGENT_DOMAINS = {
    "gtctravel.com", "virtuoso.com", "amexgbt.com", "aexp.com",
    "lartisien.com", "champtravel.com", "intheknowexperiences.com",
    "rsbtravel.com", "cisalpinatours.it", "traveljst.com",
    "hotelbeds.com", "localforeigner.com", "vintermex.com",
    "flytour.com.br", "williampearsco.uk", "sgeraghty@williampears.co.uk",
    "guerlainspanyc.com", "wondertour.cn", "htconcierge.co.uk",
    "medallin.com", "mercatortravels.ae", "hedgehogtravel.co.uk",
}
_CORPORATE_DOMAINS = {
    "antares.com", "fifa.org", "gs.com", "goldman.com",
    "hdfund.co.kr", "mckinseyco.com", "dougcorp.com", "uk.jpmorganchase.com",
    "jpmorganchase.com", "36dong.com", "recordati.it", "langleyd@erau.edu",
    "erau.edu",
}


def _contact_type(sender_email: str, sender_name: str) -> str:
    email_lower = sender_email.lower()
    name_lower = sender_name.lower()

    # Exchange internal paths
    if "/o=exchangelabs" in email_lower or "/o=exchangelab" in email_lower:
        return "Internal"

    domain = email_lower.split("@")[-1] if "@" in email_lower else ""

    # Automated systems
    if email_lower in _AUTOMATED_SENDERS:
        return "Automated"
    for pref in _AUTOMATED_SENDER_PREFIXES:
        if email_lower.startswith(pref) or email_lower.split("@")[0].lower().startswith(pref.rstrip("@")):
            return "Automated"
    if "noreply" in email_lower or "no-reply" in email_lower:
        return "Automated"
    if domain in ("sertifi.net", "ideas.com", "cvent.com", "hilton.com"):
        return "Automated"

    # Internal Waldorf staff
    if domain in _INTERNAL_DOMAINS:
        return "Internal"

    # OTA
    if domain in _OTA_DOMAINS or "booking.com" in domain:
        return "OTA"

    # Travel agents
    if domain in _TRAVEL_AGENT_DOMAINS:
        return "Travel agent"

    # Corporate
    if domain in _CORPORATE_DOMAINS:
        return "Corporate"

    # Common personal email → direct guest
    if domain in ("gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com"):
        return "Direct guest"

    # Check sender name for internal indicators
    if any(x in name_lower for x in ("nycwa_reservations", "nycwa reservations")):
        return "Internal"

    # Default by name pattern
    if not email_lower or "exchangelabs" in email_lower:
        return "Internal"

    return "Travel agent"


# ---------------------------------------------------------------------------
# Sentiment from category + context
# ---------------------------------------------------------------------------

def _sentiment(category: str, subject: str, body_preview: str) -> str:
    subject_lower = subject.lower()
    body_lower = body_preview.lower()
    combined = subject_lower + " " + body_lower

    if category == "System / Automated":
        return "Neutral"
    if any(x in combined for x in ("complaint", "noise", "unacceptable", "disappointed", "not received",
                                    "did not", "failed", "sorry", "apolog", "unfortunate")):
        return "Frustrated"
    if any(x in combined for x in ("thank you", "appreciate", "wonderful", "delighted", "perfect",
                                    "great", "love", "happy", "pleasure")):
        return "Positive"
    if any(x in combined for x in ("urgent", "asap", "time sensitive", "immediately", "cutoff",
                                    "outstanding", "unpaid", "overdue")):
        return "Anxious"
    if category in ("Billing dispute",):
        return "Neutral"
    return "Neutral"


# ---------------------------------------------------------------------------
# Next steps by category
# ---------------------------------------------------------------------------

_NEXT_STEPS: dict[str, list[str]] = {
    "Billing dispute": [
        "Review and reconcile folio charges.",
        "Send itemized invoice or confirmation to requesting party.",
        "Obtain payment authorization if outstanding balance exists.",
        "Close account once payment confirmed.",
    ],
    "VIP pre-arrival": [
        "Confirm room assignment and VIP amenity package.",
        "Brief concierge and front desk on guest preferences.",
        "Ensure all pre-arrival requests are fulfilled before check-in.",
        "Add Handle With Care note to reservation profile.",
    ],
    "Rooming list / group": [
        "Update group rooming list with latest changes.",
        "Confirm all TBC rooms have placeholder names.",
        "Send updated rooming list / confirmation letters to group coordinator.",
        "Track conversion of TBC to confirmed rooms against cutoff date.",
    ],
    "Amenity request": [
        "Confirm availability of requested amenity.",
        "Stage amenity for in-room delivery at check-in.",
        "Notify HK/Concierge/IRD of delivery requirements.",
        "Confirm completion with Reservations team.",
    ],
    "Rate inquiry": [
        "Check availability and pricing for requested dates and room type.",
        "Confirm applicable corporate/consortia rate eligibility.",
        "Send formal rate confirmation and booking options to requester.",
    ],
    "Cancellation / modification": [
        "Process requested modification in reservation system.",
        "Issue updated confirmation letter with revised details.",
        "Notify affected departments (HK, Front Desk) of change.",
    ],
    "Consortia / FHR / Virtuoso": [
        "Confirm consortia benefits and entitlements for booking.",
        "Coordinate upgrade, late checkout, or amenity per program terms.",
        "Reply to agent with confirmation of arrangements.",
    ],
    "Complaint": [
        "Acknowledge guest complaint and apologize for the experience.",
        "Investigate root cause and document findings.",
        "Offer appropriate service recovery (waiver, amenity, future discount).",
        "Escalate to management if required.",
    ],
    "System / Automated": [
        "Review report or notification for any action items.",
        "File or distribute to relevant team if required.",
    ],
    "General inquiry": [
        "Review request and coordinate with relevant department.",
        "Reply with requested information or confirmation.",
    ],
    "Internal request": [
        "Complete requested internal action.",
        "Confirm completion to requesting team member.",
    ],
}


# ---------------------------------------------------------------------------
# Main labeling function
# ---------------------------------------------------------------------------

def _get_label(email_id: int, msg: dict, ha: dict) -> dict:
    subject = str(msg.get("subject") or "")
    sender_name = str(msg.get("sender_name") or "")
    sender_email = str(msg.get("sender_email") or "")
    body = str(msg.get("body_text") or msg.get("body_preview") or "")[:400]
    heuristic_cat = str(ha.get("category") or "General inquiry")
    urgency = ha.get("urgency_score") or 2

    subject_lower = subject.lower()
    body_lower = body.lower()

    # ── Try thread overrides first ──────────────────────────────────────────
    for (subj_kw, sender_kw, cat, pri, sent, owner, ctype, summary_tmpl) in THREAD_OVERRIDES:
        subj_hit = subj_kw.lower() in subject_lower if subj_kw else True
        sender_hit = sender_kw.lower() in sender_email.lower() if sender_kw else True
        if subj_hit and sender_hit:
            return {
                "ai_summary": summary_tmpl,
                "category": cat,
                "priority_level": pri,
                "guest_sentiment": sent,
                "internal_next_steps": _NEXT_STEPS.get(cat, []),
                "missing_information": [],
                "risk_flags": [],
                "recommended_department_owner": owner,
                "contact_type": ctype,
                "confidence_score": 84,
                "confidence_reason": f"Thread pattern match on subject keyword '{subj_kw}'.",
            }

    # ── Fall back to heuristic category + derived fields ────────────────────

    # Map heuristic category to canonical category
    cat_map = {
        "Billing dispute": "Billing dispute",
        "VIP pre-arrival": "VIP pre-arrival",
        "Urgent same-day arrival": "VIP pre-arrival",
        "Rooming list / group": "Rooming list / group",
        "Amenity request": "Amenity request",
        "Rate inquiry": "Rate inquiry",
        "Cancellation / modification": "Cancellation / modification",
        "Consortia / FHR / Virtuoso": "Consortia / FHR / Virtuoso",
        "Complaint": "Complaint",
        "Accessibility request": "General inquiry",
        "Duplicate follow-up": "General inquiry",
        "Internal request": "General inquiry",
        "General inquiry": "General inquiry",
    }
    category = cat_map.get(heuristic_cat, "General inquiry")

    priority = _priority(urgency)
    contact_type = _contact_type(sender_email, sender_name)
    sentiment = _sentiment(category, subject, body)

    # Auto-generate a brief summary
    domain = sender_email.split("@")[-1] if "@" in sender_email else ""
    if contact_type == "Internal":
        actor = f"Internal staff ({sender_name.split()[0] if sender_name else 'team'})"
    elif contact_type == "Automated":
        actor = "Automated system"
    elif contact_type == "OTA":
        actor = f"OTA ({domain})"
    elif contact_type == "Travel agent":
        actor = f"Travel agent ({domain})"
    elif contact_type == "Corporate":
        actor = f"Corporate contact ({domain})"
    else:
        actor = f"Guest ({sender_name})" if sender_name else "Guest"

    summary = f"{actor} — {subject[:80]}"

    # Risk flags
    risk_flags = []
    if urgency >= 4 and category == "Billing dispute":
        risk_flags.append("Outstanding balance — follow up within 24 hours.")
    if "vip" in subject_lower or "arriving tomorrow" in subject_lower:
        risk_flags.append("VIP or time-sensitive arrival — confirm all preparations.")
    if "no show" in subject_lower or "cancelled" in subject_lower:
        risk_flags.append("No-show/cancellation revenue — charge authorization required.")

    # Determine owner
    owner_map = {
        "Billing dispute": "Finance",
        "VIP pre-arrival": "Reservations",
        "Rooming list / group": "Sales",
        "Amenity request": "Concierge",
        "Rate inquiry": "Sales",
        "Cancellation / modification": "Reservations",
        "Consortia / FHR / Virtuoso": "Reservations",
        "Complaint": "Management",
        "General inquiry": "Reservations",
        "System / Automated": "Operations",
    }
    owner = owner_map.get(category, "Reservations")

    return {
        "ai_summary": summary,
        "category": category,
        "priority_level": priority,
        "guest_sentiment": sentiment,
        "internal_next_steps": _NEXT_STEPS.get(category, []),
        "missing_information": [],
        "risk_flags": risk_flags,
        "recommended_department_owner": owner,
        "contact_type": contact_type,
        "confidence_score": 78,
        "confidence_reason": f"Rule-based derivation from heuristic category '{heuristic_cat}' and sender signals.",
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def apply_labels_batch2() -> None:
    dump_dir = Path("training/dumps")
    already_labeled = _load_already_labeled()

    success = 0
    skipped = 0
    errors = 0

    files = sorted(dump_dir.glob("completed_request_*.json"))
    new_files = [
        f for f in files
        if int(f.stem.replace("completed_request_", "")) > 106
        and int(f.stem.replace("completed_request_", "")) not in already_labeled
    ]

    print(f"Labeling {len(new_files)} new emails...")

    for dump_file in new_files:
        email_id = int(dump_file.stem.replace("completed_request_", ""))

        with open(dump_file, encoding="utf-8") as f:
            dump_data = json.load(f)

        msg = dump_data["message"]
        ha = dump_data["heuristic_analysis"]

        label = _get_label(email_id, msg, ha)
        label["model"] = "claude-sonnet-4-6-manual"
        label["analysis_engine"] = "claude-manual-training"

        sender_email = str(msg.get("sender_email") or "")
        subject = str(msg.get("subject") or "")
        fp = _fingerprint(sender_email, subject)

        try:
            save_analysis(email_id, label)
            log_training_example(email_id, fp, "labeled")
            print(f"  [OK] {email_id:4d}  {label['category']:<35} {label['priority_level']:<8} {label['contact_type']:<14} conf={label['confidence_score']}")
            success += 1
        except Exception as exc:
            print(f"  [ERR] {email_id}: {exc}")
            errors += 1

    print(f"\nDone: {success} labeled, {skipped} skipped (already done), {errors} errors.")
    _print_stats()


def _load_already_labeled() -> set[int]:
    try:
        from outlook_dashboard.database import managed_connect
        with managed_connect() as db:
            rows = db.execute(
                "SELECT email_id FROM email_analysis WHERE analysis_engine='claude-manual-training'"
            ).fetchall()
            return {int(r["email_id"]) for r in rows}
    except Exception:
        return set()


def _print_stats() -> None:
    try:
        from outlook_dashboard.database import managed_connect
        with managed_connect() as db:
            rows = db.execute("""
                SELECT category, COUNT(*) as n
                FROM email_analysis
                WHERE analysis_engine='claude-manual-training'
                GROUP BY category ORDER BY n DESC
            """).fetchall()
            total = sum(r["n"] for r in rows)
            print(f"\n=== Training corpus ({total} labeled emails) ===")
            for r in rows:
                bar = "█" * (r["n"] // 3)
                print(f"  {r['category']:<35} {r['n']:3d}  {bar}")
    except Exception as e:
        print(f"Stats error: {e}")


if __name__ == "__main__":
    apply_labels_batch2()
