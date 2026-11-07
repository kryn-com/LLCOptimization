import math
import pytest
from llc_engine import *


def orig(box_1, addl, box_5, agi, st_tax, a8r, rate=0.0425):
    """Original app logic (2025, NC) kept as a regression oracle."""
    clean_agi = agi - a8r; cst = max(0, st_tax - a8r); total = box_1 + addl
    adj = cst - (clean_agi - 12750) if cst > 0 else 0
    def sc(inc):
        inc = min(inc, box_5); new = clean_agi + inc
        ft = irs_round(max(0, new - 15750))
        if ft <= 0: tax = 0
        else:
            ti = math.floor(ft/50)*50+25 if ft < 100000 else ft
            if ti <= 11925: raw = ti*.10
            elif ti <= 48475: raw = 11925*.10 + (ti-11925)*.12
            elif ti <= 103350: raw = 11925*.10 + (48475-11925)*.12 + (ti-48475)*.22
            else: raw = 11925*.10 + (48475-11925)*.12 + (103350-48475)*.22 + (ti-103350)*.24
            tax = irs_round(raw)
        nct = irs_round(max(0, new - 12750 + adj)); nct_tax = irs_round(nct*rate)
        q = max(0, total - max(0, box_5 - inc)); cr = irs_round(min(min(2000, q*.2), tax))
        return {"inc": inc, "net": cr - (tax + nct_tax), "credit": cr}
    mn = max(0, box_5 - total); base = sc(mn); best = base
    for i in range(int(mn), min(int(box_5), int(mn)+10000)+1):
        r = sc(i)
        if r["net"] > best["net"]: best = r
    return base, best


@pytest.mark.parametrize("args", [
    (13552, 0, 14235, 4000, 0, 0), (11703, 0, 9837, 0, 0, 0),
    (20000, 500, 12000, 15000, 2400, 0), (9000, 300, 15000, 30000, 17250, 0),
    (13552, 0, 14235, 18687, 5937, 14235)])
def test_nc_2025_matches_original(args):
    b, o = optimize_scholarship(*args, year=2025, state="NC")
    ob, oo = orig(*args)
    assert (b["inclusion"], b["credit"], b["net_position"]) == (ob["inc"], ob["credit"], ob["net"])
    assert (o["inclusion"], o["credit"], o["net_position"]) == (oo["inc"], oo["credit"], oo["net"])


def test_year_constants():
    assert FED[2025]["std"] == 15750 and FED[2026]["std"] == 16100
    assert STATES["NC"]["years"][2025]["brackets"][0][1] == .0425
    assert STATES["NC"]["years"][2026]["brackets"][0][1] == .0399


def test_georgia_constants_and_tax():
    ga = STATES["GA"]["years"]
    assert ga[2025]["std"] == 12000 and ga[2025]["brackets"] == [(0, .0519)]
    assert ga[2026]["std"] == 15000 and ga[2026]["brackets"] == [(0, .0499)]
    assert state_tax(20000, "GA", 2026) == irs_round(20000 * .0499)
    assert state_tax(0, "GA", 2026) == 0


def test_nm_brackets_2026():
    assert NM_BRACKETS == [(0, .015), (5500, .032), (16500, .043), (33500, .047), (66500, .049), (210000, .059)]


def test_federal_tax_known_values():
    assert fed_tax(0, 2026) == 0
    assert fed_tax(12400, 2026) == 1243


def test_fed_tax_exact_2026_150k():
    expected = irs_round(12400*.10 + (50400-12400)*.12 + (105700-50400)*.22 + (150000-105700)*.24)
    assert fed_tax(150000, 2026) == expected


def test_nm_table_matches_official_examples():
    assert state_tax(12050, "NM", 2025) == 292
    assert state_tax(25350, "NM", 2025) == 815
    assert state_tax(49950, "NM", 2025) == 1939
    assert state_tax(12000, "NM", 2025) == 292 and state_tax(12099, "NM", 2025) == 292
    assert state_tax(60000, "NM", 2025) == 2413


def test_nm_over_100k_uses_official_schedule():
    assert state_tax(100000, "NM", 2025) == 4356
    assert state_tax(150000, "NM", 2025) == irs_round(4356 + 50000 * .049)
    assert state_tax(210000, "NM", 2025) == 9746
    assert state_tax(300000, "NM", 2025) == irs_round(9746 + 90000 * .059)


def test_ny_rates_change_between_years():
    assert state_tax(8000, "NY", 2026) < state_tax(8000, "NY", 2025)


def test_phaseout():
    assert phaseout_ratio(80000) == 1 and phaseout_ratio(90000) == 0 and phaseout_ratio(85000) == .5


def test_credit_never_exceeds_tax_and_cap_all_states():
    for year in (2025, 2026):
        for state in STATES:
            b, o = optimize_scholarship(13552, 0, 14235, 3000, 0, 0, year, state, flat_rate=0.05)
            for r in (b, o):
                assert 0 <= r["credit"] <= min(2000, r["fed_tax"])
            assert o["net_position"] >= b["net_position"]


def test_schedule_1a_lowers_federal_taxable_income():
    args = (12000, 0, 8000, 28000, 15250, 0)
    b0, o0 = optimize_scholarship(*args, year=2026, state="NC", sched_1a=0)
    b1, o1 = optimize_scholarship(*args, year=2026, state="NC", sched_1a=3000)
    assert b1["fed_taxable"] == b0["fed_taxable"] - 3000
    assert b1["fed_tax"] < b0["fed_tax"]
    assert b1["agi"] == b0["agi"]


def test_schedule_1a_can_remove_federal_tax_and_credit():
    b, o = optimize_scholarship(12000, 0, 8000, 28000, 15250, 0, 2026, "NC", sched_1a=20000)
    assert b["fed_tax"] == 0 and o["credit"] == 0
    assert o["net_position"] >= b["net_position"]


def test_default_sched_1a_is_zero():
    a = optimize_scholarship(12000, 0, 8000, 28000, 15250, 0, 2026, "NC")
    b = optimize_scholarship(12000, 0, 8000, 28000, 15250, 0, 2026, "NC", sched_1a=0)
    assert a == b


def test_georgia_optimization_runs_both_years():
    for year in (2025, 2026):
        std = STATES["GA"]["years"][year]["std"]
        agi = 28000
        b, o = optimize_scholarship(12000, 0, 8000, agi, agi - std, 0, year, "GA")
        assert o["net_position"] >= b["net_position"]
        assert o["state_tax"] >= b["state_tax"]


def test_prepare_baseline_pre_entry_adds_funding():
    agi, st, a8r = prepare_baseline("pre", 5000, 0, 2000, 0, 2026, "NC")
    assert agi == 7000 and st == 0 and a8r == 0


def test_prepare_baseline_post_entry_strips_1098t_only():
    agi, st, a8r = prepare_baseline("post", 20000, 7000, 2000, 6000, 2026, "NY")
    assert (agi, st, a8r) == (20000, 7000, 4000)


def test_rate_summary_georgia():
    assert rate_summary("GA", 2026) == "Georgia income tax rate: 4.99% (flat)"


# ---- flat-rate option ----

def test_flat_is_last_in_state_list():
    assert list(STATES.keys())[-1] == "FLAT"


def test_flat_rate_summary_uses_slider_value():
    assert rate_summary("FLAT", 2026, 0.0450) == "State income tax rate: 4.50% (flat)"


def test_flat_matches_equivalent_named_state():
    """A flat 3.99% with a $12,750 deduction must reproduce NC 2026 exactly."""
    args = (12000, 0, 8000, 28000, 15250, 0)
    nc = optimize_scholarship(*args, year=2026, state="NC")
    fl = optimize_scholarship(*args, year=2026, state="FLAT", flat_rate=.0399, flat_std=12750)
    for i in (0, 1):
        for k in ("inclusion", "credit", "fed_tax", "state_taxable", "state_tax", "net_position"):
            assert nc[i][k] == fl[i][k]


def test_flat_deduction_cancels_when_state_taxable_is_known():
    args = (12000, 0, 8000, 28000, 15250, 0)
    a = optimize_scholarship(*args, year=2026, state="FLAT", flat_rate=.05, flat_std=0)
    b = optimize_scholarship(*args, year=2026, state="FLAT", flat_rate=.05, flat_std=9000)
    assert a[1]["state_taxable"] == b[1]["state_taxable"]
    assert a[1]["inclusion"] == b[1]["inclusion"]


def test_flat_deduction_shelters_income_when_state_taxable_is_zero():
    """With $0 state taxable income, a larger entered deduction means less added state tax."""
    args = (12000, 0, 8000, 6000, 0, 0)
    _, none = optimize_scholarship(*args, year=2026, state="FLAT", flat_rate=.05, flat_std=0)
    _, big = optimize_scholarship(*args, year=2026, state="FLAT", flat_rate=.05, flat_std=10000)
    assert big["state_tax"] <= none["state_tax"]


def test_flat_zero_rate_adds_no_state_tax():
    b, o = optimize_scholarship(12000, 0, 8000, 28000, 15250, 0, 2026, "FLAT", flat_rate=0.0)
    assert b["state_tax"] == 0 and o["state_tax"] == 0


def test_marginal_rates_reported():
    _, o = optimize_scholarship(12000, 0, 8000, 28000, 15250, 0, 2026, "NC")
    assert o["fed_marginal"] == .12 and o["state_marginal"] == .0399
