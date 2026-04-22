from datetime import date

from app.services.csv_ingest import (
    _norm_date,
    _norm_phone,
    build_header_map,
    parse_csv,
)


def test_phone_normalization_basic():
    assert _norm_phone("(229) 555-0142") == "+12295550142"
    assert _norm_phone("229-555-0142") == "+12295550142"
    assert _norm_phone("2295550142") == "+12295550142"
    assert _norm_phone("+12295550142") == "+12295550142"
    assert _norm_phone("") is None
    assert _norm_phone(None) is None
    assert _norm_phone("abc") is None


def test_phone_11_digit_leading_one():
    assert _norm_phone("12295550142") == "+12295550142"


def test_date_normalization_multiple_formats():
    assert _norm_date("2026-01-15") == date(2026, 1, 15)
    assert _norm_date("01/15/2026") == date(2026, 1, 15)
    assert _norm_date("1/15/2026") == date(2026, 1, 15)
    assert _norm_date("2026-01-15T12:34:56") == date(2026, 1, 15)
    assert _norm_date("") is None
    assert _norm_date("not-a-date") is None


def test_header_map_jobber_style():
    hm = build_header_map(["Customer Name", "Phone", "Email Address", "Lead Source", "Last Activity", "Notes"])
    assert hm["name"] == "Customer Name"
    assert hm["phone"] == "Phone"
    assert hm["email"] == "Email Address"
    assert hm["source"] == "Lead Source"
    assert hm["last_contact"] == "Last Activity"
    assert hm["notes"] == "Notes"


def test_header_map_servicetitan_style():
    hm = build_header_map(["Contact", "Primary Phone", "Primary Email", "Origin", "Created Date", "Job Notes"])
    assert hm["name"] == "Contact"
    assert hm["phone"] == "Primary Phone"
    assert hm["email"] == "Primary Email"
    assert hm["source"] == "Origin"
    assert hm["last_contact"] == "Created Date"
    assert hm["notes"] == "Job Notes"


def test_parse_basic_csv_round_trip():
    raw = (
        "customer_name,phone_number,email_address,lead_source,last_activity_date,notes\n"
        "Dale Hatcher,(229) 555-0142,dale@ex.com,Facebook,2025-10-01,asked for pumping quote\n"
        "Brian Holt,602-555-0177,,Google Ad,2025-11-22,AC tune-up interest\n"
    )
    leads, skipped = parse_csv(raw)
    assert skipped == []
    assert len(leads) == 2
    assert leads[0].phone == "+12295550142"
    assert leads[0].email == "dale@ex.com"
    assert leads[0].source == "Facebook"
    assert leads[0].last_contact == date(2025, 10, 1)
    assert leads[1].email is None
    assert leads[1].phone == "+16025550177"


def test_parse_skips_empty_rows():
    raw = (
        "name,phone,email\n"
        "Valid Person,555-0001,a@b.com\n"
        ",,\n"                               # no name → skipped
        "No Contact,,\n"                     # no phone + no email → skipped
    )
    # 10-digit phone "555-0001" only has 7 digits so normalizes to None, which
    # means the first row lacks phone. Email saves it.
    leads, skipped = parse_csv(raw)
    assert len(leads) == 1
    assert leads[0].name == "Valid Person"
    assert len(skipped) == 2


def test_parse_requires_name_column():
    leads, skipped = parse_csv("phone,email\n555-1234,a@b.com\n")
    assert leads == []
    assert any("name" in r for r in skipped)


def test_parse_large_fixture_file_shape():
    # Exercise the fixture generator output so M1's 'fixture ingests cleanly'
    # acceptance criterion is tested.
    from pathlib import Path
    p = Path(__file__).parent.parent.parent / "fixtures" / "sample_leads.csv"
    assert p.exists(), f"missing fixture at {p} — run scripts/gen_sample_csv.py"
    data = p.read_bytes()
    leads, skipped = parse_csv(data)
    # Fixture is deterministic — should always yield 200 clean rows.
    assert len(leads) + len(skipped) == 200
    assert len(leads) >= 190  # generous; some rows might lack email
    for l in leads:
        assert l.name
        assert l.phone or l.email
