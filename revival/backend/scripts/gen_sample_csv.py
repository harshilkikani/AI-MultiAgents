# Why this exists: deterministic 200-row CSV generator so test fixtures stay
# reproducible but feel realistic (mix of verticals, sources, last-contact ages).
from __future__ import annotations

import csv
import random
from datetime import date, timedelta
from pathlib import Path

FIRST_NAMES = [
    "Dale", "Darlene", "Mike", "Priya", "Brian", "Ray", "Tina", "Howie", "Amelia",
    "Bertha", "Danny", "Janelle", "Carlos", "Brianna", "Alyssa", "Tom", "Stephanie",
    "Derek", "Marcus", "Jaylen", "Wanda", "Lamar", "Odessa", "Chuck", "Reba",
    "Hank", "Lorraine", "Vern", "Cheryl", "Buddy", "Doris", "Gus", "Bernice",
    "Otis", "Maybelle", "Earl", "Francine", "Roy", "Peggy", "Jimmy", "Edna",
    "Clyde", "Mabel", "Leon", "Gladys", "Wilbur", "Thelma", "Floyd", "Agnes",
    "Claude", "Mildred",
]
LAST_NAMES = [
    "Hatcher", "Calloway", "Shah", "Holt", "Kowalski", "Browne", "Keller", "Park",
    "Lane", "Ortega", "Porter", "Ramirez", "Fortner", "Chen", "Delgado", "Owens",
    "Jensen", "Briggs", "Medina", "Harmon", "Whitfield", "McAllister", "Ruiz",
    "Beckett", "Stanton", "Pickett", "Akeredolu", "Dunham", "Woodard", "Voss",
    "Bledsoe", "Crenshaw", "Pettigrew", "Driscoll", "Holcomb", "Tanaka", "Vargas",
    "Alonzo", "Cartwright", "Whittaker",
]

VERTICALS = ["septic", "roofing", "hvac", "plumbing", "electrical"]
VERTICAL_WEIGHTS = [0.3, 0.25, 0.25, 0.12, 0.08]

SOURCES = [
    "Facebook Lead Ad", "Google Ad", "Website form", "Referral",
    "Instagram DM", "Phone inquiry", "LinkedIn", "Newsletter", "Home Show",
]
SOURCE_WEIGHTS = [0.22, 0.18, 0.20, 0.10, 0.08, 0.10, 0.04, 0.05, 0.03]

NOTE_TEMPLATES = {
    "septic": [
        "Wanted a pumping quote, said 'next week' and went cold.",
        "Tank age unknown, asked about install pricing.",
        "Had a backup, we couldn't get there same-day.",
        "Asked about maintenance contract, went quiet.",
    ],
    "roofing": [
        "Hail inspection requested, never set a time.",
        "Asked about warranty on a 12-year-old roof.",
        "Wanted a commercial flat-roof quote.",
        "Had a leak, called competitor instead.",
    ],
    "hvac": [
        "Furnace tune-up, said 'ask me again in fall.'",
        "AC quote, no follow-up after estimate sent.",
        "Heat pump inquiry, budget was tight.",
        "Duct cleaning interest, cycled out.",
    ],
    "plumbing": [
        "Water heater replacement quote never closed.",
        "Leak repair, said 'my uncle can do it.'",
        "Garbage disposal install, went dark.",
        "Pipe repair, price-shopping.",
    ],
    "electrical": [
        "Panel upgrade quote, stalled on permit question.",
        "EV charger install inquiry, went dark.",
        "Outlet install ask, tiny job so we skipped.",
        "Whole-house surge protector estimate, no reply.",
    ],
}

AREA_CODES = [
    229, 404, 770, 912,     # GA
    303, 719, 720,          # CO
    602, 480, 520,          # AZ
    713, 281, 832,          # TX
    412, 717, 215,          # PA
]


def gen(n: int, seed: int = 42) -> list[dict]:
    rng = random.Random(seed)
    today = date(2026, 4, 22)
    rows = []
    for _ in range(n):
        fn = rng.choice(FIRST_NAMES)
        ln = rng.choice(LAST_NAMES)
        name = f"{fn} {ln}"
        vert = rng.choices(VERTICALS, weights=VERTICAL_WEIGHTS, k=1)[0]
        source = rng.choices(SOURCES, weights=SOURCE_WEIGHTS, k=1)[0]
        ac = rng.choice(AREA_CODES)
        phone = f"({ac}) 555-{rng.randint(1000, 9999):04d}"
        # Realistic distribution: most old leads are 3-18 months stale.
        days_old = int(rng.triangular(60, 540, 180))
        last = today - timedelta(days=days_old)
        email_ok = rng.random() > 0.3
        email = f"{fn.lower()}.{ln.lower()}@{rng.choice(['gmail.com','yahoo.com','outlook.com','aol.com'])}" if email_ok else ""
        note = rng.choice(NOTE_TEMPLATES[vert])
        rows.append({
            "customer_name": name,
            "phone_number": phone,
            "email_address": email,
            "lead_source": source,
            "last_activity_date": last.isoformat(),
            "notes": note,
        })
    return rows


def main():
    rows = gen(200)
    out = Path(__file__).parent.parent / "fixtures" / "sample_leads.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} rows -> {out}")


if __name__ == "__main__":
    main()
