"""The onboarding quiz. The frontend renders it from GET /quiz, so this is the single source."""

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
PARTS = {"AM": "morning", "PM": "afternoon", "EVE": "evening"}
SLOTS = [f"{d}-{p}" for d in DAYS for p in PARTS]

AREAS = [
    {"value": "coding", "label": "Coding"},
    {"value": "writing", "label": "Writing"},
    {"value": "design", "label": "Design"},
    {"value": "research", "label": "Research"},
    {"value": "presenting", "label": "Presenting"},
    {"value": "organising", "label": "Organising"},
]

QUESTIONS = [
    {
        "id": "best_time",
        "text": "When do you do your best work?",
        "type": "single",
        "options": [
            {"value": "early", "label": "Early morning"},
            {"value": "day", "label": "Daytime"},
            {"value": "evening", "label": "Evening"},
            {"value": "night", "label": "After 10 PM"},
        ],
    },
    {
        "id": "rhythm",
        "text": "How do you usually approach a deadline?",
        "type": "single",
        "options": [
            {"value": "steady", "label": "Start early and keep a steady pace"},
            {"value": "bursts", "label": "Bursts of work across the weeks"},
            {"value": "sprinter", "label": "Mostly in the last few days"},
        ],
    },
    {"id": "enjoy", "text": "Which parts do you enjoy most? (up to 2)", "type": "multi", "max": 2, "options": AREAS},
    {"id": "avoid", "text": "Which parts would you rather avoid? (up to 2)", "type": "multi", "max": 2, "options": AREAS},
    {
        "id": "channel",
        "text": "How should the team reach you?",
        "type": "single",
        "options": [
            {"value": "whatsapp", "label": "WhatsApp"},
            {"value": "discord", "label": "Discord"},
            {"value": "teams", "label": "Microsoft Teams"},
            {"value": "email", "label": "Email"},
        ],
    },
    {
        "id": "reply",
        "text": "How fast do you usually reply to the group?",
        "type": "single",
        "options": [
            {"value": "hour", "label": "Within an hour"},
            {"value": "day", "label": "Same day"},
            {"value": "nextday", "label": "Next day"},
        ],
    },
    {
        "id": "meetings",
        "text": "What kind of meetings work for you?",
        "type": "single",
        "options": [
            {"value": "short", "label": "Short and frequent"},
            {"value": "long", "label": "Few and long"},
            {"value": "async", "label": "Async updates only"},
        ],
    },
    {
        "id": "availability",
        "text": "When are you usually free for a team meeting?",
        "type": "slots",
        "options": [{"value": s, "label": s} for s in SLOTS],
    },
    {"id": "commitments", "text": "Fixed commitments this month (classes, job shifts)?", "type": "text"},
    {
        "id": "stuck",
        "text": "When you're stuck, you usually...",
        "type": "single",
        "options": [
            {"value": "ask", "label": "Ask the team right away"},
            {"value": "alone", "label": "Try alone first"},
            {"value": "quiet", "label": "Go a bit quiet"},
        ],
    },
    {
        "id": "frustration",
        "text": "One thing past teammates did that frustrated you (private: only your twin sees this)",
        "type": "text",
        "private": True,
    },
]

PRIVATE_KEYS = {q["id"] for q in QUESTIONS if q.get("private")}

SLOT_LABEL = {s: f"{s.split('-')[0]} {PARTS[s.split('-')[1]]}" for s in SLOTS}
