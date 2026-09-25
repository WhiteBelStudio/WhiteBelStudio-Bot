from datetime import datetime, timezone

from app.services.pvp import PVP_KINDS, _make_round


def test_pvp_catalog_rounds_are_valid():
    for kind in PVP_KINDS:
        round_ = _make_round(kind)
        assert round_.kind == kind
        assert round_.prompt
        assert round_.answer


def test_pvp_round_math_is_numeric():
    round_ = _make_round("math")
    assert round_.answer.isdigit()


def test_pvp_round_sequence_is_numeric():
    round_ = _make_round("sequence")
    assert round_.answer.isdigit()
