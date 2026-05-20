"""Apply manual AI training labels to all 50 completed_request dump files.

Run from repo root:  python training/apply_labels.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from outlook_dashboard.database import save_analysis, log_training_example
from outlook_dashboard.training_pipeline import _fingerprint, _subject_tokens

# ---------------------------------------------------------------------------
# Label definitions
# Each dict key = email_id (int).
# Fields match save_analysis() schema.
# ---------------------------------------------------------------------------

LABELS: dict[int, dict] = {

    # ── Automated / system emails ────────────────────────────────────────────

    57: {
        "ai_summary": "Automated Hilton OnQ Reservation Activity Extract report for NYCWA. Routine daily/weekly report replacing the decommissioned Reservation Activity by Agent report. No guest-facing action required.",
        "category": "System / Automated",
        "priority_level": "Low",
        "guest_sentiment": "Neutral",
        "internal_next_steps": ["File or review reservation activity report as needed.", "Contact gro.support@hilton.com with any report questions."],
        "missing_information": [],
        "risk_flags": [],
        "recommended_department_owner": "Operations",
        "contact_type": "Automated",
        "confidence_score": 97,
        "confidence_reason": "Clearly automated noreply Hilton system report; no ambiguity.",
    },

    58: {
        "ai_summary": "Automated Booking.com arrival notification listing reservations with today's or tomorrow's arrival date at Waldorf Astoria New York. Informational only.",
        "category": "System / Automated",
        "priority_level": "Low",
        "guest_sentiment": "Neutral",
        "internal_next_steps": ["Review arriving reservations list and cross-reference with front desk.", "Flag any discrepancies in reservation details."],
        "missing_information": [],
        "risk_flags": [],
        "recommended_department_owner": "Operations",
        "contact_type": "OTA",
        "confidence_score": 96,
        "confidence_reason": "Standard automated OTA arrivals notification; no action beyond review.",
    },

    81: {
        "ai_summary": "Automated DocuSign CC notification — Chris Song has been copied on a signature request from Waldorf Astoria New York. No reply action needed; recipient must action the DocuSign link directly.",
        "category": "System / Automated",
        "priority_level": "Low",
        "guest_sentiment": "Neutral",
        "internal_next_steps": ["Confirm intended signatory has completed DocuSign request.", "Follow up if unsigned after 24 hours."],
        "missing_information": [],
        "risk_flags": [],
        "recommended_department_owner": "Operations",
        "contact_type": "Automated",
        "confidence_score": 95,
        "confidence_reason": "DocuSign CC notification — clearly automated, no guest inquiry.",
    },

    # ── Signature Suite / VVIP Inquiry ───────────────────────────────────────

    59: {
        "ai_summary": "Luigi Romaniello (internal Sales) responding to Ritam Bhalla (In the Know Experiences, GTC/Virtuoso) re: VVIP client requesting a 5-6 bedroom Signature Suite. Luigi confirms partnership value and commits to sending a full proposal the following morning.",
        "category": "VIP pre-arrival",
        "priority_level": "High",
        "guest_sentiment": "Positive",
        "internal_next_steps": ["Send full Signature Suite proposal to Ritam Bhalla by next morning.", "Confirm suite availability and pricing for client's dates.", "Loop in Sales Director for VVIP account management."],
        "missing_information": ["Guest name and arrival/departure dates", "Number of guests in party", "Rate plan / GTC preferred rates"],
        "risk_flags": ["VVIP multi-suite request — limited inventory risk if dates not confirmed promptly."],
        "recommended_department_owner": "Sales",
        "contact_type": "Travel agent",
        "confidence_score": 91,
        "confidence_reason": "Internal outbound response to Virtuoso/GTC agent; suite inquiry is high-value pipeline.",
    },

    62: {
        "ai_summary": "Ritam Bhalla (In the Know Experiences, Global Travel Collection / GTC SELECT / Virtuoso agent, NYC) requesting a 5-6 bedroom Signature Suite for a VVIP client. Virtuoso partnership agent with existing relationship with David and Luigi.",
        "category": "VIP pre-arrival",
        "priority_level": "High",
        "guest_sentiment": "Positive",
        "internal_next_steps": ["Send detailed Signature Suite proposal with availability and rates.", "Assign dedicated Sales Manager (David/Luigi) as main contact.", "Prepare VVIP profile and amenity plan once booking confirmed."],
        "missing_information": ["Arrival and departure dates", "Guest name and party size", "Budget / rate expectations", "Special requests"],
        "risk_flags": ["VVIP client via top-tier Virtuoso partner — any delay in response risks losing the booking."],
        "recommended_department_owner": "Sales",
        "contact_type": "Travel agent",
        "confidence_score": 93,
        "confidence_reason": "Clear Virtuoso/GTC VVIP suite inquiry; high commercial value.",
    },

    # ── VIP Szor Arrival / Amenity Recovery ─────────────────────────────────

    60: {
        "ai_summary": "Marina Judkins (internal Reservations) responding to Amy re VIP Szor arrival — amenity was not delivered as requested despite being arranged pre-arrival. Marina apologizes, confirms room was cleaned and repairs scheduled for tonight.",
        "category": "VIP pre-arrival",
        "priority_level": "High",
        "guest_sentiment": "Apologetic",
        "internal_next_steps": ["Confirm amenity re-delivery completed tonight.", "Document service recovery in guest profile for Szor family.", "Notify manager of amenity delivery failure for training purposes."],
        "missing_information": ["Confirmation that amenity was re-delivered", "Root cause of original delivery failure"],
        "risk_flags": ["Amenity failure for VIP guest — service recovery must be documented and escalated if repeated."],
        "recommended_department_owner": "Reservations",
        "contact_type": "Internal",
        "confidence_score": 88,
        "confidence_reason": "Internal service recovery on VIP arrival; amenity failure requires documented follow-through.",
    },

    61: {
        "ai_summary": "Duplicate of email 60 — Marina Judkins VIP Szor amenity service recovery note. Same content as prior message in thread.",
        "category": "VIP pre-arrival",
        "priority_level": "High",
        "guest_sentiment": "Apologetic",
        "internal_next_steps": ["See completed_request_60 for action items."],
        "missing_information": [],
        "risk_flags": ["Duplicate — check for threading/import issue in pipeline."],
        "recommended_department_owner": "Reservations",
        "contact_type": "Internal",
        "confidence_score": 85,
        "confidence_reason": "Duplicate of email 60 detected by identical content.",
    },

    # ── Stay Certificate / Date Modification ────────────────────────────────

    63: {
        "ai_summary": "Sabata Sarcone (Assistant Director of Rooms, internal) sending brief thank-you acknowledgment, likely in response to Dakota confirming the stay certificate date change. No further action required.",
        "category": "General inquiry",
        "priority_level": "Low",
        "guest_sentiment": "Positive",
        "internal_next_steps": ["No action required — acknowledgment only."],
        "missing_information": [],
        "risk_flags": [],
        "recommended_department_owner": "Reservations",
        "contact_type": "Internal",
        "confidence_score": 90,
        "confidence_reason": "One-line internal thank-you; no actionable content.",
    },

    67: {
        "ai_summary": "Dakota Weglarz (internal Reservations) confirming to Sabata Sarcone that the stay certificate reservation date has been updated and a confirmation letter has been sent to the guest.",
        "category": "General inquiry",
        "priority_level": "Low",
        "guest_sentiment": "Positive",
        "internal_next_steps": ["Confirm guest received updated confirmation letter.", "Update reservation notes if stay certificate terms changed."],
        "missing_information": [],
        "risk_flags": [],
        "recommended_department_owner": "Reservations",
        "contact_type": "Internal",
        "confidence_score": 90,
        "confidence_reason": "Straightforward internal confirmation; no risk.",
    },

    76: {
        "ai_summary": "Sabata Sarcone (Assistant Director of Rooms) forwarding guest request to move stay certificate reservation to Sunday–Monday June 7–8. Requesting response as soon as possible.",
        "category": "Cancellation / modification",
        "priority_level": "Normal",
        "guest_sentiment": "Neutral",
        "internal_next_steps": ["Check availability for June 7–8 and confirm if date change is possible under stay certificate terms.", "Reply to Sabata with confirmation or alternative dates.", "Issue updated confirmation letter if approved."],
        "missing_information": ["Stay certificate terms and any blackout date restrictions", "Current reservation dates and confirmation number"],
        "risk_flags": [],
        "recommended_department_owner": "Reservations",
        "contact_type": "Internal",
        "confidence_score": 89,
        "confidence_reason": "Clear internal date-change request for stay certificate; standard modification workflow.",
    },

    # ── LVMH Rate Inquiry ────────────────────────────────────────────────────

    64: {
        "ai_summary": "Jasmin Howanietz (internal Sales) acknowledging LVMH rate inquiry from Mauricio Fonseca (flytour.com.br), advising that David will follow up with options.",
        "category": "Rate inquiry",
        "priority_level": "Normal",
        "guest_sentiment": "Neutral",
        "internal_next_steps": ["David to follow up with LVMH rate options and availability for July 16–20.", "Confirm commission structure for flytour.com.br."],
        "missing_information": [],
        "risk_flags": [],
        "recommended_department_owner": "Sales",
        "contact_type": "Internal",
        "confidence_score": 88,
        "confidence_reason": "Internal holding response to corporate rate inquiry; Sales owns follow-up.",
    },

    65: {
        "ai_summary": "Duplicate of email 64 — Jasmin Howanietz LVMH rate acknowledgment to Mauricio Fonseca.",
        "category": "Rate inquiry",
        "priority_level": "Normal",
        "guest_sentiment": "Neutral",
        "internal_next_steps": ["See completed_request_64 for action items."],
        "missing_information": [],
        "risk_flags": ["Duplicate — check for threading/import issue."],
        "recommended_department_owner": "Sales",
        "contact_type": "Internal",
        "confidence_score": 85,
        "confidence_reason": "Duplicate of email 64.",
    },

    66: {
        "ai_summary": "Mauricio Fonseca (flytour.com.br, Brazilian luxury travel agency) requesting LVMH corporate rate for 2 double rooms, July 16–20, for a VIP client. Also requesting commission confirmation.",
        "category": "Rate inquiry",
        "priority_level": "Normal",
        "guest_sentiment": "Neutral",
        "internal_next_steps": ["Check availability and pricing for 2 double rooms July 16–20 under LVMH corporate rate.", "Confirm commission rate for flytour.com.br.", "Send formal rate confirmation and booking options."],
        "missing_information": ["Guest names", "LVMH employee verification / rate eligibility confirmation"],
        "risk_flags": [],
        "recommended_department_owner": "Sales",
        "contact_type": "Travel agent",
        "confidence_score": 91,
        "confidence_reason": "Clear corporate rate inquiry with specific dates from established Brazilian luxury agency.",
    },

    # ── Dakota / Arielle Matza Pet Service Thread ────────────────────────────

    68: {
        "ai_summary": "Dakota Weglarz (internal Reservations) advising that express shipping for a dog robe cannot be guaranteed to arrive during the guest's stay. Offering to reschedule the service.",
        "category": "Amenity request",
        "priority_level": "Normal",
        "guest_sentiment": "Apologetic",
        "internal_next_steps": ["Await guest response on reschedule preference.", "Explore in-house dog robe alternatives for the current stay."],
        "missing_information": ["Guest preference: reschedule or in-house alternative?"],
        "risk_flags": [],
        "recommended_department_owner": "Concierge",
        "contact_type": "Internal",
        "confidence_score": 87,
        "confidence_reason": "Internal coordination on pet amenity availability; low risk.",
    },

    70: {
        "ai_summary": "Arielle Matza (guest, gmail.com, attorney at Grubman Shire) acknowledging Dakota's message about check-in time and expressing appreciation for Yorkie 'Sammi' arrangements.",
        "category": "Amenity request",
        "priority_level": "Normal",
        "guest_sentiment": "Positive",
        "internal_next_steps": ["Confirm all Bark Avenue pet package items are staged for arrival.", "Note guest works in entertainment law — Handle With Care profile."],
        "missing_information": [],
        "risk_flags": [],
        "recommended_department_owner": "Concierge",
        "contact_type": "Direct guest",
        "confidence_score": 89,
        "confidence_reason": "Positive guest response; guest identity confirmed (Grubman Shire attorney).",
    },

    71: {
        "ai_summary": "Arielle Matza (guest) noting that the robe offered is too large for her Yorkie Sammi (Hershey is bigger). Asking urgently if a smaller robe can be rushed for tomorrow's arrival.",
        "category": "Amenity request",
        "priority_level": "High",
        "guest_sentiment": "Anxious",
        "internal_next_steps": ["Confirm smallest available robe size with HK immediately.", "If no smaller size available, source alternative or notify guest.", "Prioritize robe resolution before 5.20 arrival."],
        "missing_information": ["Smallest available robe size in inventory"],
        "risk_flags": ["Guest arriving tomorrow — time-sensitive resolution required tonight."],
        "recommended_department_owner": "Concierge",
        "contact_type": "Direct guest",
        "confidence_score": 91,
        "confidence_reason": "Time-sensitive pet amenity request for arrival tomorrow.",
    },

    72: {
        "ai_summary": "Bret Campbell (Director of Housekeeping) confirming that a small robe has been set aside in the HK office for Arielle Matza's dog.",
        "category": "Amenity request",
        "priority_level": "Normal",
        "guest_sentiment": "Neutral",
        "internal_next_steps": ["Deliver robe to guest room at arrival.", "Confirm delivery completion with Reservations team."],
        "missing_information": [],
        "risk_flags": [],
        "recommended_department_owner": "Concierge",
        "contact_type": "Internal",
        "confidence_score": 93,
        "confidence_reason": "Director of HK confirming robe availability — resolution step.",
    },

    78: {
        "ai_summary": "Dakota Weglarz (internal) confirming that she contacted Arielle Matza directly and instructed HK to include the small robe in the Bark Avenue package even if slightly oversized so the guest can take photos.",
        "category": "Amenity request",
        "priority_level": "Normal",
        "guest_sentiment": "Neutral",
        "internal_next_steps": ["Confirm Bark Avenue package fully assembled with robe.", "Confirm delivery upon guest check-in."],
        "missing_information": [],
        "risk_flags": [],
        "recommended_department_owner": "Concierge",
        "contact_type": "Internal",
        "confidence_score": 92,
        "confidence_reason": "Internal resolution confirmation for pet robe.",
    },

    80: {
        "ai_summary": "Dakota Weglarz (internal) confirming with HK that small dog robes are available. Also noting custom smaller robes are on order, referencing 'Hershey' the dog model. Warm, personalized response style consistent with Handle With Care guest.",
        "category": "Amenity request",
        "priority_level": "Normal",
        "guest_sentiment": "Positive",
        "internal_next_steps": ["Confirm robe is staged for Arielle Matza arrival.", "Track custom robe order for future HWC pet guests."],
        "missing_information": [],
        "risk_flags": [],
        "recommended_department_owner": "Concierge",
        "contact_type": "Internal",
        "confidence_score": 90,
        "confidence_reason": "Internal HK/Concierge coordination; personalized pet service.",
    },

    84: {
        "ai_summary": "Daniel Harpaz (internal) sending photos showing exact Bark Avenue pet package setup for Arielle Matza's arrival tomorrow (May 20). Tags HK Coordinators and IRD: include 4 dog booties (not 2), references Dakota for additional notes. Handle With Care guest.",
        "category": "Amenity request",
        "priority_level": "High",
        "guest_sentiment": "Neutral",
        "internal_next_steps": ["HK: set up pet package per attached photos with 4 booties.", "IRD: prepare dog-friendly amenity items per photos.", "Confirm setup completion before guest arrival."],
        "missing_information": [],
        "risk_flags": ["Multi-department coordination required before TOMORROW arrival — confirm all teams acknowledged."],
        "recommended_department_owner": "Concierge",
        "contact_type": "Internal",
        "confidence_score": 94,
        "confidence_reason": "Urgent pre-arrival multi-department coordination with specific instructions and photos.",
    },

    92: {
        "ai_summary": "Dakota Weglarz (internal) tagging HK Coordinators via email to confirm all Bark Avenue pet gifts are ready and available for delivery to Arielle Matza's room upon arrival tomorrow. Flags guest as Handle With Care. Also tags IRD.",
        "category": "Amenity request",
        "priority_level": "High",
        "guest_sentiment": "Neutral",
        "internal_next_steps": ["HK Coordinators: confirm all pet package items staged.", "IRD: confirm readiness for in-room delivery.", "Ensure reply confirming readiness is sent to Dakota before EOD."],
        "missing_information": ["Confirmation reply from HK Coordinators and IRD"],
        "risk_flags": ["Arrival tomorrow — no confirmation received yet from HK/IRD at time of email."],
        "recommended_department_owner": "Concierge",
        "contact_type": "Internal",
        "confidence_score": 93,
        "confidence_reason": "Clear pre-arrival HWC coordination; risks if teams don't confirm.",
    },

    96: {
        "ai_summary": "Dakota Weglarz (internal) responding to Arielle Matza — confirms CharDOGnay (dog-friendly champagne) is ordered, advises check-in likely ~4pm due to sold-out hotel, placed Handle With Care note to prioritize room assignment.",
        "category": "Amenity request",
        "priority_level": "Normal",
        "guest_sentiment": "Positive",
        "internal_next_steps": ["Confirm CharDOGnay delivery to room.", "Monitor room availability and prioritize Arielle Matza's check-in as early as possible.", "Keep HWC note active through entire stay."],
        "missing_information": [],
        "risk_flags": ["Hotel sold out — check-in delay ~4pm may disappoint guest; proactive communication recommended."],
        "recommended_department_owner": "Concierge",
        "contact_type": "Internal",
        "confidence_score": 92,
        "confidence_reason": "Guest-facing service coordination; sold-out flag is a minor risk.",
    },

    98: {
        "ai_summary": "Arielle Matza (guest) sending photos of her Yorkie Sammi and herself for the birthday celebration. Selects CharDOGnay, asks about check-in time. Warm, enthusiastic tone. Guest is celebrating a birthday.",
        "category": "Amenity request",
        "priority_level": "Normal",
        "guest_sentiment": "Positive",
        "internal_next_steps": ["Confirm check-in time and proactively manage expectations for potential late room availability.", "Ensure birthday amenity is staged alongside Bark Avenue package.", "Add birthday note to guest profile."],
        "missing_information": [],
        "risk_flags": [],
        "recommended_department_owner": "Concierge",
        "contact_type": "Direct guest",
        "confidence_score": 92,
        "confidence_reason": "Enthusiastic guest engagement for birthday stay; high personalization opportunity.",
    },

    # ── Waldorf Security Group Rooming List ─────────────────────────────────

    69: {
        "ai_summary": "NYCWA_Reservations (Chris Song) sending updated confirmation letters and rooming list to Kimberly for the Waldorf Security team group block.",
        "category": "Rooming list / group",
        "priority_level": "Normal",
        "guest_sentiment": "Neutral",
        "internal_next_steps": ["Confirm Kimberly received all confirmation letters.", "Note any changes in rooming list for front desk."],
        "missing_information": [],
        "risk_flags": [],
        "recommended_department_owner": "Sales",
        "contact_type": "Internal",
        "confidence_score": 88,
        "confidence_reason": "Standard group rooming list update; no risk.",
    },

    # ── Arielle Matza / Hilton Honors initial contact ────────────────────────
    # (email 70 covered above; no separate entry needed)

    # ── Singapore Exchange Group ─────────────────────────────────────────────

    73: {
        "ai_summary": "Hazel Limfat (Specialty Markets Manager, internal) responding to Chase Hegwood re Singapore Exchange Group July 2026 deposit. Clarifies she was confused with another Singapore group in September. Requests Chase check with her before contacting clients directly to preserve seamless guest experience.",
        "category": "Rooming list / group",
        "priority_level": "Normal",
        "guest_sentiment": "Neutral",
        "internal_next_steps": ["Hazel to follow up with client on 1st deposit for Singapore Exchange Group.", "Internal process reminder: coordinate internally before client outreach on payment matters."],
        "missing_information": ["Confirmation of payment status for SGX group July 2026"],
        "risk_flags": ["Payment timeline may have slipped — verify deposit received or outstanding."],
        "recommended_department_owner": "Sales",
        "contact_type": "Internal",
        "confidence_score": 86,
        "confidence_reason": "Internal coordination on group deposit; minor process concern.",
    },

    74: {
        "ai_summary": "Chase Hegwood (internal, likely Revenue/Reservations) noting that the Singapore Exchange Group deposit appears due per FDC Booking Deposit Report but not posted in OnQ. Requesting clarification from Hazel.",
        "category": "Rooming list / group",
        "priority_level": "Normal",
        "guest_sentiment": "Neutral",
        "internal_next_steps": ["Verify Singapore Exchange Group deposit status in both FDC and OnQ.", "Post deposit in OnQ if received but not logged.", "Follow up with client if deposit is genuinely outstanding."],
        "missing_information": ["Confirmation of whether deposit was physically received", "OnQ posting confirmation"],
        "risk_flags": ["Deposit discrepancy between FDC report and OnQ — potential accounting gap."],
        "recommended_department_owner": "Sales",
        "contact_type": "Internal",
        "confidence_score": 87,
        "confidence_reason": "System reconciliation issue on group deposit — needs Finance/Sales verification.",
    },

    77: {
        "ai_summary": "Hazel Limfat (internal) confirming to Chase that the Singapore Exchange Group deposit team has already received payment 1–2 weeks ago. Reiterates process request: check internally before reaching out to client.",
        "category": "Rooming list / group",
        "priority_level": "Normal",
        "guest_sentiment": "Neutral",
        "internal_next_steps": ["Post deposit to OnQ if not already done.", "Document process guidance: Sales to validate internally before client contact on payment."],
        "missing_information": [],
        "risk_flags": [],
        "recommended_department_owner": "Sales",
        "contact_type": "Internal",
        "confidence_score": 89,
        "confidence_reason": "Deposit received; issue is OnQ posting and internal process, not guest risk.",
    },

    # ── QCC Waldorf Group ────────────────────────────────────────────────────

    79: {
        "ai_summary": "Tammy Benedict (QCC/Goldman Sachs event planner) thanking Chris for the rooming list update and advising she is working to finalize remaining inductee reservations. Asks Waldorf to stand by.",
        "category": "Rooming list / group",
        "priority_level": "Normal",
        "guest_sentiment": "Positive",
        "internal_next_steps": ["Hold TBC rooms pending QCC final count.", "Follow up with Tammy Benedict in 24–48 hours if no update received."],
        "missing_information": ["Final inductee count and room assignments"],
        "risk_flags": ["Group block TBC rooms require timely confirmation to avoid inventory issues."],
        "recommended_department_owner": "Sales",
        "contact_type": "Corporate",
        "confidence_score": 88,
        "confidence_reason": "External group planner (Goldman Sachs QCC event); pending final numbers.",
    },

    82: {
        "ai_summary": "NYCWA_Reservations confirming to QCC/Goldman Sachs that the pick-up report has been sent to another email chain, and Hanna Lynch has been added as event planner to the Cvent Passkey portal.",
        "category": "Rooming list / group",
        "priority_level": "Normal",
        "guest_sentiment": "Neutral",
        "internal_next_steps": ["Confirm Hanna Lynch's Cvent access is active.", "Share Cvent portal link with QCC planners."],
        "missing_information": [],
        "risk_flags": [],
        "recommended_department_owner": "Sales",
        "contact_type": "Internal",
        "confidence_score": 89,
        "confidence_reason": "Standard group portal access and reporting coordination.",
    },

    83: {
        "ai_summary": "NYCWA_Reservations (internal) sending QCC Goldman Sachs updated rooming list with latest reservations, TBC placeholders, shared room notes, and billing updates. TBC rooms have been created and are available via Cvent portal.",
        "category": "Rooming list / group",
        "priority_level": "Normal",
        "guest_sentiment": "Neutral",
        "internal_next_steps": ["Confirm QCC planners (Heather/Christina/Tammy) have reviewed updated list.", "Track TBC rooms for timely conversion to confirmed bookings."],
        "missing_information": ["Final confirmation of TBC rooms"],
        "risk_flags": ["Multiple TBC placeholders — conversion deadline should be monitored."],
        "recommended_department_owner": "Sales",
        "contact_type": "Internal",
        "confidence_score": 90,
        "confidence_reason": "Detailed group rooming list with open TBC items requiring follow-through.",
    },

    # ── Local Foreigner / Kouracos Rate ─────────────────────────────────────

    85: {
        "ai_summary": "Katie Simms (Local Foreigner luxury travel agency) requesting written confirmation that Michael Kouracos can use his complimentary 3rd night to guarantee a late checkout on June 11 without penalty.",
        "category": "Rate inquiry",
        "priority_level": "Normal",
        "guest_sentiment": "Neutral",
        "internal_next_steps": ["Confirm in writing: 3rd night complimentary entitles guest to late checkout without penalty.", "Add confirmation to reservation notes.", "Reply to Katie Simms with written confirmation."],
        "missing_information": ["Exact checkout time requested"],
        "risk_flags": [],
        "recommended_department_owner": "Reservations",
        "contact_type": "Travel agent",
        "confidence_score": 90,
        "confidence_reason": "Travel agent requesting written late-checkout guarantee; standard documentation request.",
    },

    86: {
        "ai_summary": "Katie Simms (Local Foreigner) requesting a confirmation letter for Michael Kouracos that includes the deposit amount and cancellation policy, which are missing from the letter currently on file.",
        "category": "Rate inquiry",
        "priority_level": "Normal",
        "guest_sentiment": "Neutral",
        "internal_next_steps": ["Regenerate confirmation letter with deposit and cancellation policy included.", "Email updated letter to Katie Simms.", "Verify cancellation policy matches current rate plan terms."],
        "missing_information": [],
        "risk_flags": ["Missing deposit/cancellation terms on confirmation letter — legal/compliance risk if disputed."],
        "recommended_department_owner": "Reservations",
        "contact_type": "Travel agent",
        "confidence_score": 92,
        "confidence_reason": "Clear documentation gap on confirmation letter; straightforward fix.",
    },

    # ── Anticipated Arrivals ─────────────────────────────────────────────────

    87: {
        "ai_summary": "Brian Tarabocchia (Rooms Experience Manager, internal) circulating the anticipated arrivals list for May 20, 2026. Routine pre-arrival team briefing communication.",
        "category": "General inquiry",
        "priority_level": "Normal",
        "guest_sentiment": "Neutral",
        "internal_next_steps": ["Review attached arrivals list and confirm VIP/HWC flags with relevant teams.", "Brief front desk and concierge on notable arrivals.", "Confirm any VIP pre-arrival preparations are on track."],
        "missing_information": [],
        "risk_flags": [],
        "recommended_department_owner": "Operations",
        "contact_type": "Internal",
        "confidence_score": 93,
        "confidence_reason": "Standard internal pre-arrival briefing from Rooms Experience Manager.",
    },

    # ── Viajes Intermex Late Checkout (Reservation 3460311383) ───────────────

    88: {
        "ai_summary": "Dakota Weglarz (internal Reservations) confirming to Joelle Monsonego that late checkout is approved — guest can check out at 2pm or later. No penalty applies.",
        "category": "Cancellation / modification",
        "priority_level": "Low",
        "guest_sentiment": "Positive",
        "internal_next_steps": ["Note 2pm late checkout in reservation and front desk system.", "Notify housekeeping of delayed departure."],
        "missing_information": [],
        "risk_flags": [],
        "recommended_department_owner": "Reservations",
        "contact_type": "Internal",
        "confidence_score": 95,
        "confidence_reason": "Clear internal confirmation of approved late checkout; resolved.",
    },

    94: {
        "ai_summary": "Joelle Monsonego (Viajes Intermex, Mexico travel agent) confirming guest prefers to check out May 20 at approximately 2pm. References 3rd night free promotion as reason no penalty should apply. Asks for confirmation.",
        "category": "Cancellation / modification",
        "priority_level": "Normal",
        "guest_sentiment": "Positive",
        "internal_next_steps": ["Confirm 2pm late checkout in system.", "Reply to Joelle confirming no penalty under 3rd Night Free promo.", "Notify housekeeping."],
        "missing_information": [],
        "risk_flags": [],
        "recommended_department_owner": "Reservations",
        "contact_type": "Travel agent",
        "confidence_score": 92,
        "confidence_reason": "Travel agent confirming late checkout date/time; pending written confirmation.",
    },

    95: {
        "ai_summary": "Duplicate of email 94 — Joelle Monsonego late checkout confirmation request.",
        "category": "Cancellation / modification",
        "priority_level": "Normal",
        "guest_sentiment": "Positive",
        "internal_next_steps": ["See completed_request_94 for action items."],
        "missing_information": [],
        "risk_flags": ["Duplicate — check for threading/import issue."],
        "recommended_department_owner": "Reservations",
        "contact_type": "Travel agent",
        "confidence_score": 85,
        "confidence_reason": "Duplicate of email 94.",
    },

    97: {
        "ai_summary": "NYCWA_Reservations (internal) responding to Joelle Monsonego with late checkout options under the Third Night Free promotion — room stays reserved and guest may check out at any time if checking out on the final night.",
        "category": "Cancellation / modification",
        "priority_level": "Normal",
        "guest_sentiment": "Positive",
        "internal_next_steps": ["Confirm guest's checkout decision.", "Update reservation notes with confirmed 2pm checkout."],
        "missing_information": ["Guest's final checkout time confirmation"],
        "risk_flags": [],
        "recommended_department_owner": "Reservations",
        "contact_type": "Internal",
        "confidence_score": 91,
        "confidence_reason": "Internal outbound clarifying 3rd Night Free policy; pending guest decision.",
    },

    104: {
        "ai_summary": "Joelle Monsonego (Viajes Intermex travel agent) requesting late checkout at 2pm on May 20 for guest on Reservation 3460311383 under Third Night Free promotion, with no penalty. Asks for confirmation.",
        "category": "Cancellation / modification",
        "priority_level": "Normal",
        "guest_sentiment": "Positive",
        "internal_next_steps": ["Confirm 2pm late checkout, no penalty, under 3rd Night Free promo terms.", "Send written confirmation to Joelle.", "Update front desk and HK."],
        "missing_information": [],
        "risk_flags": [],
        "recommended_department_owner": "Reservations",
        "contact_type": "Travel agent",
        "confidence_score": 93,
        "confidence_reason": "Standard travel agent late checkout request with promotional backing.",
    },

    105: {
        "ai_summary": "Duplicate of email 104 — Joelle Monsonego late checkout request for Reservation 3460311383.",
        "category": "Cancellation / modification",
        "priority_level": "Normal",
        "guest_sentiment": "Positive",
        "internal_next_steps": ["See completed_request_104 for action items."],
        "missing_information": [],
        "risk_flags": ["Duplicate — check for threading/import issue."],
        "recommended_department_owner": "Reservations",
        "contact_type": "Travel agent",
        "confidence_score": 85,
        "confidence_reason": "Duplicate of email 104.",
    },

    # ── Kricheli Family Billing ──────────────────────────────────────────────

    89: {
        "ai_summary": "Olga Arkhangelskaya (billing contact, likely travel agent or client representative) querying whether a dry cleaning charge was already included in the final Kricheli folio at $93,167.83. Asks Chris to confirm to avoid double billing.",
        "category": "Billing dispute",
        "priority_level": "High",
        "guest_sentiment": "Neutral",
        "internal_next_steps": ["Review Kricheli Nicol and Avaram folios to confirm whether dry cleaning charge was included in the $93,167.83 total.", "Reply to Olga with clear line-item confirmation.", "If already included, provide updated folio showing zero balance for that line."],
        "missing_information": ["Itemized folio breakdown confirming dry cleaning line item"],
        "risk_flags": ["Outstanding balance complexity — Kricheli family has multiple folios across rooms/incidentals; double-billing risk if not reconciled carefully."],
        "recommended_department_owner": "Reservations",
        "contact_type": "Travel agent",
        "confidence_score": 90,
        "confidence_reason": "Billing dispute with external contact; potential double-charge on luxury folio.",
    },

    99: {
        "ai_summary": "NYCWA_Reservations (Chris Song) attaching Kricheli family folios for review: Nicol Kricheli Room & Tax ($6,731.03 outstanding), Nicol Kricheli Incidentals ($4,675.11 outstanding), Avaram Kricheli Late Laundry Charges. Total outstanding is substantial.",
        "category": "Billing dispute",
        "priority_level": "High",
        "guest_sentiment": "Neutral",
        "internal_next_steps": ["Send folios to Olga Arkhangelskaya for review.", "Confirm dry cleaning allocation between Nicol and Avaram folios.", "Follow up within 24 hours for payment authorization."],
        "missing_information": ["Avaram Kricheli laundry charges total amount", "Payment method and authorization for outstanding balances"],
        "risk_flags": ["Total outstanding across folios likely exceeds $11,000+ — significant credit risk if payment is delayed."],
        "recommended_department_owner": "Reservations",
        "contact_type": "Internal",
        "confidence_score": 92,
        "confidence_reason": "High-value billing with multiple outstanding folios — urgent reconciliation needed.",
    },

    100: {
        "ai_summary": "NYCWA_Reservations (Chris Song) noting he will follow up in separate emails for two families with intricate billing. Acknowledging complexity and committing to keeping billing straight and clearly documented.",
        "category": "Billing dispute",
        "priority_level": "High",
        "guest_sentiment": "Neutral",
        "internal_next_steps": ["Send separate billing follow-ups per family.", "Document each family's folio separately with itemized totals.", "Confirm payment authorization methods for each folio."],
        "missing_information": ["Identity of second family involved in billing", "Payment timeline and authorization"],
        "risk_flags": ["Multi-family intricate billing — high error risk; ensure folios are segregated per party."],
        "recommended_department_owner": "Reservations",
        "contact_type": "Internal",
        "confidence_score": 88,
        "confidence_reason": "Internal billing coordination for complex multi-family folio; significant outstanding balance.",
    },

    # ── Long Stay Enquiry / FHR ──────────────────────────────────────────────

    101: {
        "ai_summary": "Marina Judkins (internal Reservations) responding to a long stay enquiry. FHR (Fine Hotels & Resorts) guest departing a suite tomorrow has confirmed 12pm checkout but is entitled to 4pm late checkout per FHR. Marina confirms expedited room cleaning upon departure.",
        "category": "Consortia / FHR / Virtuoso",
        "priority_level": "Normal",
        "guest_sentiment": "Positive",
        "internal_next_steps": ["Coordinate expedited room cleaning for departing FHR suite guest.", "Confirm 4pm late checkout is honored per FHR terms.", "Update front desk on suite departure timeline."],
        "missing_information": [],
        "risk_flags": ["Room readiness window tight — if guest uses 4pm late checkout, next arriving guest should be notified of potential delay."],
        "recommended_department_owner": "Reservations",
        "contact_type": "Internal",
        "confidence_score": 90,
        "confidence_reason": "FHR late checkout coordination; standard consortia entitlement.",
    },

    # ── Antares Capital Group ────────────────────────────────────────────────

    75: {
        "ai_summary": "NYCWA_Reservations (internal) confirming to Naida Basu (Antares Capital VP Client Events) the group math: keeping 46 room nights at $1,250 covers the $57,278.75 shortfall to meet the 85% minimum. Inventory updated to fulfill request.",
        "category": "Rooming list / group",
        "priority_level": "Normal",
        "guest_sentiment": "Neutral",
        "internal_next_steps": ["Confirm updated room block inventory matches Naida's request.", "Issue revised group contract/confirmation showing updated room count.", "Coordinate credit card authorizations for named guests."],
        "missing_information": ["Remaining 3 names for June 8–11 still outstanding"],
        "risk_flags": ["3 room names still TBC — credit card authorizations will be blocked until resolved."],
        "recommended_department_owner": "Sales",
        "contact_type": "Internal",
        "confidence_score": 91,
        "confidence_reason": "Group block math confirmed; pending names/CCA items need tracking.",
    },

    93: {
        "ai_summary": "Naida Basu (Antares Capital) noting she still owes 3 names for June 8–11. Directing credit card authorizations for 3 specific guests (Hyunkoo Kim, Bumsoo Cho, Hee Eun Park) to Yelim Lee at hdfund.co.kr on June 9.",
        "category": "Rooming list / group",
        "priority_level": "Normal",
        "guest_sentiment": "Neutral",
        "internal_next_steps": ["Send credit card authorization forms to yllee@hdfund.co.kr for Kim, Cho, Park rooms on June 9.", "Follow up with Naida for 3 outstanding names for June 8–11.", "Update rooming list with HD Fund contact for billing."],
        "missing_information": ["3 outstanding names for June 8–11"],
        "risk_flags": ["Payment authorization routed to third-party entity (HD Fund) — verify billing relationship before processing."],
        "recommended_department_owner": "Sales",
        "contact_type": "Corporate",
        "confidence_score": 89,
        "confidence_reason": "Group billing routing to external fund — payment verification step is important.",
    },

    102: {
        "ai_summary": "Naida Basu (Antares Capital VP Client Events) requesting to keep specific room nights (June 9: 10 rooms, June 10–11: 18 rooms each) and release remaining rooms. Net 46 room nights at $1,250 to cover $57,278.75 shortfall. Requests Passkey be reopened.",
        "category": "Rooming list / group",
        "priority_level": "Normal",
        "guest_sentiment": "Neutral",
        "internal_next_steps": ["Update Antares Capital room block per specific dates and counts.", "Release rooms not being held.", "Reopen Passkey for group.", "Assign placeholder names 'Antares Capital' to unnamed rooms."],
        "missing_information": ["Final guest names for unnamed rooms"],
        "risk_flags": ["Passkey closure/reopen mid-block cycle — ensure group contract reflects updated minimums."],
        "recommended_department_owner": "Sales",
        "contact_type": "Corporate",
        "confidence_score": 91,
        "confidence_reason": "Clear room block restructuring request from corporate event coordinator.",
    },

    103: {
        "ai_summary": "NYCWA_Reservations (internal) detailing reservation history for Bob Sternfels (McKinsey & Company): three reservations under his name. Reservation 1875729544 (canceled), Reservation 3424383037 (GDS booking, not canceled, check-in protection note, keys unclear). Internal coordination note.",
        "category": "VIP pre-arrival",
        "priority_level": "High",
        "guest_sentiment": "Neutral",
        "internal_next_steps": ["Verify status of Reservation 3424383037 — check if keys were made.", "Confirm check-in protection is active in system.", "Notify Front Desk of VIP status for Bob Sternfels (McKinsey CEO).", "Coordinate with all teams for seamless check-in."],
        "missing_information": ["Whether keys were made for Reservation 3424383037", "Whether reservation is still active"],
        "risk_flags": ["GDS booking with ambiguous key/check-in status for high-profile McKinsey CEO — requires immediate verification."],
        "recommended_department_owner": "Reservations",
        "contact_type": "Internal",
        "confidence_score": 90,
        "confidence_reason": "High-profile VIP with reservation ambiguity; risk of check-in failure for CEO-level guest.",
    },

    106: {
        "ai_summary": "NYCWA_Reservations (internal) responding to Naida Basu (Antares Capital), apologizing for missed phone call and confirming all room block adjustments and confirmation letter updates will be coordinated by email for clear documentation.",
        "category": "Rooming list / group",
        "priority_level": "Normal",
        "guest_sentiment": "Positive",
        "internal_next_steps": ["Send updated room block confirmation letters to Naida Basu.", "Document all changes by email per agreed communication method.", "Confirm all open items (names, CCA) are resolved."],
        "missing_information": ["Updated confirmation letters still to be sent"],
        "risk_flags": [],
        "recommended_department_owner": "Sales",
        "contact_type": "Internal",
        "confidence_score": 89,
        "confidence_reason": "Internal outbound response to corporate client; documentation-by-email protocol confirmed.",
    },

    # ── VIP Arriving Tomorrow: Iverson & Klingel ─────────────────────────────

    90: {
        "ai_summary": "Jasmin Howanietz (internal Sales) confirming to Julia (likely Virtuoso/travel agent) that Mr. Tim Iverson, Mr. Robert Klingel and their families are confirmed for tomorrow (May 20–24). Personal Concierge team copied for arrival coordination.",
        "category": "VIP pre-arrival",
        "priority_level": "High",
        "guest_sentiment": "Positive",
        "internal_next_steps": ["Brief Personal Concierge team on Iverson & Klingel family arrival preferences.", "Confirm VIP amenities and welcome notes are staged.", "Ensure room assignments prioritize family-appropriate accommodation.", "Prepare personalized welcome for both families."],
        "missing_information": ["Number of guests per family", "Any specific requests or preferences on file"],
        "risk_flags": [],
        "recommended_department_owner": "Reservations",
        "contact_type": "Internal",
        "confidence_score": 93,
        "confidence_reason": "Virtuoso VIP families arriving tomorrow; high-priority pre-arrival coordination confirmed.",
    },

    91: {
        "ai_summary": "Duplicate of email 90 — Jasmin Howanietz VIP Iverson & Klingel arrival confirmation.",
        "category": "VIP pre-arrival",
        "priority_level": "High",
        "guest_sentiment": "Positive",
        "internal_next_steps": ["See completed_request_90 for action items."],
        "missing_information": [],
        "risk_flags": ["Duplicate — check for threading/import issue."],
        "recommended_department_owner": "Reservations",
        "contact_type": "Internal",
        "confidence_score": 85,
        "confidence_reason": "Duplicate of email 90.",
    },
}


def apply_labels() -> None:
    dump_dir = Path("training/dumps")
    if not dump_dir.exists():
        print("No training/dumps directory found. Run the import pipeline first.")
        return

    success = 0
    skipped = 0
    missing = 0

    for dump_file in sorted(dump_dir.glob("completed_request_*.json")):
        email_id = int(dump_file.stem.replace("completed_request_", ""))
        if email_id not in LABELS:
            print(f"  [MISSING] No labels defined for email_id={email_id}")
            missing += 1
            continue

        with open(dump_file, encoding="utf-8") as f:
            dump_data = json.load(f)

        msg = dump_data["message"]
        label = dict(LABELS[email_id])
        label["model"] = "claude-sonnet-4-6-manual"
        label["analysis_engine"] = "claude-manual-training"

        sender_email = str(msg.get("sender_email") or "")
        subject = str(msg.get("subject") or "")
        fp = _fingerprint(sender_email, subject)

        try:
            save_analysis(email_id, label)
            log_training_example(email_id, fp, "labeled")
            print(f"  [OK] email_id={email_id:4d}  {label['category']:<32}  pri={label['priority_level']:<8}  conf={label['confidence_score']}")
            success += 1
        except Exception as exc:
            print(f"  [ERR] email_id={email_id}: {exc}")
            skipped += 1

    print(f"\nDone: {success} labeled, {skipped} errors, {missing} missing label definitions.")


if __name__ == "__main__":
    apply_labels()
