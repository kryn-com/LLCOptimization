from llc_engine import *
from llc_report import *


def test_gain_adds_up_to_burden_difference():
    for year in (2025, 2026):
        for state in STATES:
            b, o = optimize_scholarship(13552, 0, 14235, 4000, 0, 0, year, state)
            g = gain_breakdown(b, o)
            assert g["net_gain"] == b["tax_burden"] - o["tax_burden"]


def test_report_renders_for_all_states():
    for state in STATES:
        b, o = optimize_scholarship(11703, 0, 9837, 0, 0, 0, 2026, state)
        g = gain_breakdown(b, o)
        html = html_report(b, o, g, 11703, 0, 9837, 0, state, 2026)
        assert "NET SAVINGS" in html and STATES[state]["name"] in html
        assert state in plain_text_report(b, o, g, 11703, 0, 9837, 0, state, 2026)
        assert STATES[state]["taxable_label"] in " ".join(k for k, _ in tie_out(o, state))


def test_ny_notice_only_for_ny():
    for state in STATES:
        b, o = optimize_scholarship(12000, 0, 8000, 28000, 15250, 0, 2026, state)
        g = gain_breakdown(b, o)
        assert ("Yonkers" in html_report(b, o, g, 12000, 0, 8000, 0, state, 2026)) == (state == "NY")


def test_savings_table_has_no_percentages():
    b, o = optimize_scholarship(12000, 0, 8000, 28000, 15250, 0, 2026, "NC")
    assert "%" not in gain_html(gain_breakdown(b, o))


def test_client_explanation_names_state():
    b, o = optimize_scholarship(12000, 0, 8000, 28000, 15250, 0, 2026, "GA")
    assert "Georgia" in client_explanation(b, o, gain_breakdown(b, o), 8000, "GA", 2026)


def test_sched_1a_row_only_when_used():
    b, o = optimize_scholarship(12000, 0, 8000, 28000, 15250, 0, 2026, "NC", sched_1a=3000)
    labels = [r[0] for r in process_rows(o, 12000, 0, 8000, 0, "NC", 2026)]
    assert any("Schedule 1-A" in l for l in labels)
    b, o = optimize_scholarship(12000, 0, 8000, 28000, 15250, 0, 2026, "NC")
    labels = [r[0] for r in process_rows(o, 12000, 0, 8000, 0, "NC", 2026)]
    assert not any("Schedule 1-A" in l for l in labels)
