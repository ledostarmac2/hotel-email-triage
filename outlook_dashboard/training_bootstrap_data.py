"""Seed training examples for the local classifier bootstrap.

These are realistic hotel-email scenarios labeled by category, urgency (1-5),
and department owner. They are only inserted once; subsequent calls to
seed_bootstrap_examples() are a no-op if the table already has rows.

All category labels must match taxonomy.CATEGORIES exactly.
All owner labels must match taxonomy.DEPARTMENT_OWNERS exactly.
"""
from __future__ import annotations

# Each entry: (subject_tokens, body_redacted, label_urgency, label_owner, label_category)
# Valid categories: Accessibility request, Amenity request, Billing dispute,
#   Cancellation / modification, Complaint, Consortia / FHR / Virtuoso,
#   Duplicate follow-up, General inquiry, Internal request, Rate inquiry,
#   Rooming list / group, Urgent same-day arrival, VIP pre-arrival
# Valid owners: All Departments, Concierge, Engineering, Front Desk,
#   Housekeeping, Reservations, Sales

SEED_EXAMPLES: list[tuple[str, str, int, str, str]] = [
    # ── Urgent same-day arrival ───────────────────────────────────────────────
    (
        "arriving today 2 hours urgent room ready",
        "Our guests are landing at JFK in 2 hours and will head straight to the hotel. "
        "They need their room ready immediately upon arrival. This is extremely urgent.",
        5, "Front Desk", "Urgent same-day arrival",
    ),
    (
        "same day arrival 3pm room not ready urgent VIP",
        "Checking in today at 3pm. Guest is very VIP and the room must be fully prepared "
        "and inspected before arrival. Please prioritize this immediately.",
        5, "Front Desk", "Urgent same-day arrival",
    ),
    (
        "guest arrives tonight flight delayed room held urgent",
        "Our guest's flight was delayed and they will now arrive around midnight. "
        "Please ensure the room is held and accessible upon late arrival.",
        5, "Front Desk", "Urgent same-day arrival",
    ),
    # ── Billing dispute ───────────────────────────────────────────────────────
    (
        "billing dispute charge incorrect overcharge minibar",
        "I am reviewing my bill and see a charge of $350 for minibar that I never used. "
        "I have never touched the minibar during my entire stay and I dispute this charge entirely.",
        4, "Front Desk", "Billing dispute",
    ),
    (
        "incorrect charge credit card dispute refund",
        "There is an unauthorized charge of $240 on my credit card from your hotel. "
        "I did not authorize this and am requesting an immediate refund and explanation.",
        4, "Front Desk", "Billing dispute",
    ),
    (
        "double charged room rate invoice wrong",
        "I notice I have been charged twice for my room on the same night. "
        "Please review and correct this billing error as soon as possible.",
        3, "Front Desk", "Billing dispute",
    ),
    # ── Complaint ─────────────────────────────────────────────────────────────
    (
        "complaint noise disturbance neighbor room",
        "The noise from the room next door has been intolerable all night. I have called the front desk "
        "twice and nothing has been done. I am extremely unhappy with this experience.",
        4, "Front Desk", "Complaint",
    ),
    (
        "complaint cleanliness room condition dirty unacceptable",
        "Our room was in an unacceptable condition upon check-in. The bathroom had visible dirt "
        "and the sheets appeared to not have been changed. This is not the standard we expected.",
        4, "Front Desk", "Complaint",
    ),
    (
        "feedback poor service unhappy experience review negative",
        "I am writing to express my disappointment with the service during my recent stay. "
        "Staff were dismissive and our requests were repeatedly ignored. I expect a response.",
        3, "Front Desk", "Complaint",
    ),
    (
        "food quality restaurant dinner disappointing complaint",
        "The dinner service last night was extremely disappointing. The food was cold, "
        "the service was slow, and the staff were inattentive. This is unacceptable.",
        3, "Front Desk", "Complaint",
    ),
    # ── Cancellation / modification ───────────────────────────────────────────
    (
        "cancel reservation cancellation policy refund",
        "I need to cancel my reservation due to a family emergency. Please confirm the cancellation "
        "and refund per your cancellation policy.",
        3, "Reservations", "Cancellation / modification",
    ),
    (
        "change reservation modify dates early check in",
        "I need to modify my upcoming reservation. Could I change the check-in date to the 10th instead? "
        "My confirmation number is on file.",
        2, "Reservations", "Cancellation / modification",
    ),
    (
        "date change extend stay one more night",
        "I would like to extend my stay by one additional night if a room is available. "
        "Please let me know if this is possible and confirm the updated rate.",
        2, "Reservations", "Cancellation / modification",
    ),
    # ── General inquiry ───────────────────────────────────────────────────────
    (
        "reservation confirmation booking dates check availability",
        "Hello, I would like to confirm my reservation for two nights arriving on the 15th. "
        "Please send the confirmation details to my email address.",
        2, "Reservations", "General inquiry",
    ),
    (
        "early check in request arrival tomorrow morning",
        "Our guests will be arriving very early tomorrow around 8am due to their flight. "
        "Is it possible to arrange an early check-in? We would really appreciate it.",
        3, "Front Desk", "General inquiry",
    ),
    (
        "late checkout request departure afternoon",
        "Could you please arrange a late checkout for us? We have a flight at 6pm and would like "
        "to keep the room until 4pm. Happy to pay any applicable fee.",
        2, "Front Desk", "General inquiry",
    ),
    (
        "restaurant reservation dinner recommendation concierge",
        "Could you please book a dinner reservation for 4 guests tonight at a nice Italian restaurant "
        "nearby? We prefer somewhere quiet with good wine selection.",
        2, "Concierge", "General inquiry",
    ),
    (
        "taxi airport transfer car service pickup",
        "Please arrange airport pickup for our guest arriving at JFK Terminal 4. "
        "They will need a sedan transfer to the hotel.",
        2, "Concierge", "General inquiry",
    ),
    (
        "extra towels pillows amenities housekeeping request",
        "Could housekeeping please bring two extra pillows and additional towels to our room? "
        "We also need more coffee pods for the machine.",
        1, "Housekeeping", "Amenity request",
    ),
    (
        "maintenance AC air conditioning broken not working hot",
        "The air conditioning in our room has stopped working completely. "
        "It is very warm and uncomfortable. Please send maintenance as soon as possible.",
        4, "Engineering", "General inquiry",
    ),
    (
        "wifi internet not working connectivity issue work meetings",
        "The WiFi in our room is not connecting. I need internet access for work meetings "
        "tomorrow morning. Please help resolve this as soon as possible.",
        3, "Engineering", "General inquiry",
    ),
    (
        "lost item left behind forgotten phone laptop room",
        "I believe I left my laptop charger in room 412 during my checkout yesterday. "
        "Could you please check lost and found and let me know?",
        2, "Front Desk", "General inquiry",
    ),
    (
        "invoice receipt request corporate billing expense",
        "Could you please send me a detailed itemized invoice for my recent stay? "
        "I need it for our corporate expense report submission.",
        2, "Front Desk", "General inquiry",
    ),
    # ── VIP pre-arrival ───────────────────────────────────────────────────────
    (
        "VIP celebrity arrival special treatment amenities suite",
        "A VIP celebrity guest is arriving on Saturday and will require complete discretion, "
        "private entrance access, and a welcome amenity in the suite.",
        4, "Front Desk", "VIP pre-arrival",
    ),
    (
        "anniversary surprise flowers champagne setup room",
        "Could you please arrange for flowers and a bottle of champagne to be set up in our room "
        "before we arrive? It is our wedding anniversary and we want it to be special.",
        2, "Concierge", "VIP pre-arrival",
    ),
    (
        "birthday celebration cake setup room decoration surprise",
        "Our guest is celebrating a milestone birthday. Could you please arrange a birthday cake "
        "and some decorations to be placed in the room as a surprise?",
        2, "Concierge", "VIP pre-arrival",
    ),
    (
        "pre-arrival setup preferences welcome amenity high-profile guest",
        "This guest is a returning platinum member and requests their preferred room configuration "
        "and welcome amenity per their profile. Please confirm this is arranged.",
        3, "Front Desk", "VIP pre-arrival",
    ),
    # ── Rooming list / group ──────────────────────────────────────────────────
    (
        "group block reservation corporate conference 20 rooms",
        "We have a group of 20 guests arriving for a corporate conference on the 22nd. "
        "Please send information about group rates and availability for our room block.",
        2, "Sales", "Rooming list / group",
    ),
    (
        "rooming list wedding block 15 guests",
        "Please find attached the rooming list for the Johnson wedding block. "
        "15 rooms are needed from Friday through Sunday. Please confirm receipt.",
        2, "Reservations", "Rooming list / group",
    ),
    # ── Accessibility request ─────────────────────────────────────────────────
    (
        "wheelchair accessible room ADA accommodation disability grab bars",
        "Our guest requires a fully ADA-accessible room with roll-in shower and grab bars. "
        "Please confirm this can be accommodated before arrival.",
        3, "Front Desk", "Accessibility request",
    ),
    # ── Rate inquiry ──────────────────────────────────────────────────────────
    (
        "rate inquiry best available rate discount government corporate",
        "Could you please send me your best available rates for a 3-night stay next month? "
        "I am eligible for a corporate discount and would like to see the rates.",
        2, "Reservations", "Rate inquiry",
    ),
    # ── Consortia / FHR / Virtuoso ────────────────────────────────────────────
    (
        "FHR Amex Fine Hotels Resorts Virtuoso benefit amenity",
        "Our guest is booked through Fine Hotels and Resorts and should receive the standard "
        "FHR amenities including breakfast, room upgrade if available, and late checkout.",
        3, "Reservations", "Consortia / FHR / Virtuoso",
    ),
    (
        "Virtuoso preferred partner benefits confirmation agency",
        "This reservation is through our Virtuoso agency. Please confirm the complimentary "
        "breakfast and welcome amenity are on the booking for this guest.",
        2, "Reservations", "Consortia / FHR / Virtuoso",
    ),
    # ── Amenity request ───────────────────────────────────────────────────────
    (
        "mini fridge crib rollaway bed baby extra amenity",
        "Could you please have a rollaway bed and a mini fridge placed in our room prior to arrival? "
        "We are traveling with a young child who will need the crib setup.",
        2, "Housekeeping", "Amenity request",
    ),
    # ── Duplicate follow-up ───────────────────────────────────────────────────
    (
        "follow up checking in reminder previous request unanswered",
        "Just following up on my previous email from yesterday regarding the reservation change. "
        "I have not received a response yet. Could you please confirm?",
        2, "Reservations", "Duplicate follow-up",
    ),
    (
        "re: following up again no reply urgent please respond",
        "I have sent several emails about my upcoming stay and have not received any confirmation. "
        "This is urgent as my arrival is in 2 days. Please respond immediately.",
        3, "Reservations", "Duplicate follow-up",
    ),
    # ── Internal request ──────────────────────────────────────────────────────
    (
        "internal team update staff communication shift handover",
        "Hi team, just a reminder about the shift change protocol and handover notes "
        "for tonight's evening shift. Please review the briefing document.",
        1, "All Departments", "Internal request",
    ),
    (
        "internal memo housekeeping schedule update staff",
        "Please note the updated housekeeping schedule for this weekend. All team members "
        "should review and confirm receipt of the new assignments.",
        1, "All Departments", "Internal request",
    ),
]


def seed_bootstrap_examples(db_path=None) -> int:
    """Insert seed examples into training_bootstrap if the table is empty.

    Returns the number of rows inserted (0 if already seeded).
    """
    from .database import managed_connect
    from .text_utils import utc_now_iso
    with managed_connect(db_path) as db:
        existing = db.execute("SELECT COUNT(*) FROM training_bootstrap").fetchone()[0]
        if existing > 0:
            return 0
        now = utc_now_iso()
        db.executemany(
            "INSERT INTO training_bootstrap (subject_tokens, body_redacted, label_urgency, label_owner, label_category, source, created_at) VALUES (?,?,?,?,?,'bootstrap',?)",
            [(s, b, u, o, c, now) for s, b, u, o, c in SEED_EXAMPLES],
        )
        return len(SEED_EXAMPLES)


def get_bootstrap_examples(db_path=None) -> list[dict]:
    """Return all bootstrap seed examples in the training_examples schema format."""
    from .database import managed_connect
    with managed_connect(db_path) as db:
        rows = db.execute(
            "SELECT subject_tokens, body_redacted, label_urgency, label_owner, label_category FROM training_bootstrap"
        ).fetchall()
    return [
        {
            "subject_tokens": r[0],
            "body_redacted": r[1],
            "label_urgency": r[2],
            "label_owner": r[3],
            "label_category": r[4],
            "labeling_engine": "bootstrap",
        }
        for r in rows
    ]
