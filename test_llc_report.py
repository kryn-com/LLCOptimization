from llc_engine import *
from llc_report import *


def test_gain_adds_up_to_burden_difference():
    for year in (2025, 2026):
        for state in STATES:
            b, o = optimize_scholarship(13552, 0, 14235, 4000, 0, 0, year, state, flat_rate=0.05)
            g = gain_breakdown(b, o)
            assert g["net_gain"] == b["tax_burden"] - o["tax_burden"]


def test_report_renders_for_all_states():
    for state in STATES:
        b, o = optimize_scholarship(11703, 0, 9837, 0, 0, 0, 2026, state, flat_rate=0.05)
        g = gain_breakdown(b, o)
        html = html_report(b, o, g, 11703, 0, 9837, 0, state, 2026)
        assert "NET SAVINGS" in html
        if state != "FLAT":
            assert STATES[state]["name"] in html
        assert STATES[state]["taxable_label"] in " ".join(k for k, _ in tie_out(o, state))
        assert plain_text_report(b, o, g, 11703, 0, 9837, 0, state, 2026)


def test_ny_notice_only_for_ny():
    for state in STATES:
        b, o = optimize_scholarship(12000, 0, 8000, 28000, 15250, 0, 2026, state, flat_rate=0.05)
        g = gain_breakdown(b, o)
        assert ("Yonkers" in html_report(b, o, g, 12000, 0, 8000, 0, state, 2026)) == (state == "NY")


def test_savings_table_has_no_percentages():
    b, o = optimize_scholarship(12000, 0, 8000, 28000, 15250, 0, 2026, "NC")
    assert "%" not in gain_html(gain_breakdown(b, o))


def test_client_explanation_names_state():
    b, o = optimize_scholarship(12000, 0, 8000, 28000, 15250, 0, 2026, "GA")
    assert "Georgia" in client_explanation(b, o, gain_breakdown(b, o), 8000, "GA", 2026)


def test_flat_rate_text_never_shows_internal_code():
    b, o = optimize_scholarship(12000, 0, 8000, 28000, 15250, 0, 2026, "FLAT", flat_rate=.045, flat_std=0)
    g = gain_breakdown(b, o)
    texts = [html_report(b, o, g, 12000, 0, 8000, 0, "FLAT", 2026),
             plain_text_report(b, o, g, 12000, 0, 8000, 0, "FLAT", 2026),
             client_explanation(b, o, g, 8000, "FLAT", 2026),
             " ".join(l for l, _, _ in process_rows(o, 12000, 0, 8000, 0, "FLAT", 2026)),
             " ".join(k for k, _ in tie_out(o, "FLAT"))]
    for t in texts:
        assert "FLAT" not in t
    assert "federal and state income tax" in client_explanation(b, o, g, 8000, "FLAT", 2026)


def test_sched_1a_row_only_when_used():
    b, o = optimize_scholarship(12000, 0, 8000, 28000, 15250, 0, 2026, "NC", sched_1a=3000)
    labels = [r[0] for r in process_rows(o, 12000, 0, 8000, 0, "NC", 2026)]
    assert any("Schedule 1-A" in l for l in labels)
    b, o = optimize_scholarship(12000, 0, 8000, 28000, 15250, 0, 2026, "NC")
    labels = [r[0] for r in process_rows(o, 12000, 0, 8000, 0, "NC", 2026)]
    assert not any("Schedule 1-A" in l for l in labels)
