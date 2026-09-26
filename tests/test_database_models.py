from app.db.models import (
    CommunityReputationVote,
    CoinTransaction,
    EconomyAccount,
    PvpMatch,
    ReputationRating,
    UserInventory,
)


def _constraint_names(model: type) -> set[str]:
    return {constraint.name for constraint in model.__table__.constraints if constraint.name}


def test_reputation_constraints_exist() -> None:
    names = _constraint_names(ReputationRating)
    assert "ck_reputation_score_range" in names
    assert "ck_reputation_rating_not_self" in names


def test_community_reputation_constraints_exist() -> None:
    names = _constraint_names(CommunityReputationVote)
    assert "ck_community_reputation_votes_score" in names
    assert "ck_community_rep_vote_not_self" in names


def test_economy_constraints_exist() -> None:
    names = _constraint_names(EconomyAccount)
    assert {
        "ck_economy_balance_nonnegative",
        "ck_economy_daily_streak_nonnegative",
        "ck_economy_lifetime_earned_nonnegative",
        "ck_economy_lifetime_spent_nonnegative",
    } <= names


def test_inventory_transaction_and_pvp_constraints_exist() -> None:
    assert "ck_inventory_quantity_positive" in _constraint_names(UserInventory)
    assert "ck_coin_transaction_zero_only_gift_received" in _constraint_names(CoinTransaction)
    assert {
        "ck_pvp_match_not_self",
        "ck_pvp_match_status",
    } <= _constraint_names(PvpMatch)
