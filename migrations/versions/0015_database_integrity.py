"""Enforce database-level integrity for core domains.

Revision ID: 0015_database_integrity
Revises: 0014_remove_social_system
"""

from alembic import op
from sqlalchemy import text

revision = "0015_database_integrity"
down_revision = "0014_remove_social_system"
branch_labels = None
depends_on = None


def _assert_clean_data() -> None:
    connection = op.get_bind()
    checks = {
        "reputation_ratings.score": "SELECT 1 FROM reputation_ratings WHERE score < 1 OR score > 5 LIMIT 1",
        "reputation_ratings self-ratings": "SELECT 1 FROM reputation_ratings WHERE rater_id = rated_id LIMIT 1",
        "community reputation score": "SELECT 1 FROM community_reputation_votes WHERE score NOT IN (-1, 1) LIMIT 1",
        "community self-votes": "SELECT 1 FROM community_reputation_votes WHERE rater_id = rated_id LIMIT 1",
        "economy balance": "SELECT 1 FROM economy_accounts WHERE balance < 0 LIMIT 1",
        "economy daily streak": "SELECT 1 FROM economy_accounts WHERE daily_streak < 0 LIMIT 1",
        "economy lifetime earned": "SELECT 1 FROM economy_accounts WHERE lifetime_earned < 0 LIMIT 1",
        "economy lifetime spent": "SELECT 1 FROM economy_accounts WHERE lifetime_spent < 0 LIMIT 1",
        "inventory quantity": "SELECT 1 FROM user_inventory WHERE quantity <= 0 LIMIT 1",
        "pvp self-match": "SELECT 1 FROM pvp_matches WHERE opponent_id IS NOT NULL AND creator_id = opponent_id LIMIT 1",
    }
    for label, query in checks.items():
        if connection.execute(text(query)).first() is not None:
            raise RuntimeError(
                f"Cannot apply 0015_database_integrity: invalid existing data in {label}. "
                "Clean the data explicitly before retrying the migration."
            )


def upgrade() -> None:
    _assert_clean_data()
    op.create_check_constraint(
        "ck_reputation_rating_not_self",
        "reputation_ratings",
        "rater_id <> rated_id",
    )
    op.create_check_constraint(
        "ck_community_rep_vote_not_self",
        "community_reputation_votes",
        "rater_id <> rated_id",
    )
    op.create_check_constraint(
        "ck_economy_balance_nonnegative",
        "economy_accounts",
        "balance >= 0",
    )
    op.create_check_constraint(
        "ck_economy_daily_streak_nonnegative",
        "economy_accounts",
        "daily_streak >= 0",
    )
    op.create_check_constraint(
        "ck_economy_lifetime_earned_nonnegative",
        "economy_accounts",
        "lifetime_earned >= 0",
    )
    op.create_check_constraint(
        "ck_economy_lifetime_spent_nonnegative",
        "economy_accounts",
        "lifetime_spent >= 0",
    )
    op.create_check_constraint(
        "ck_inventory_quantity_positive",
        "user_inventory",
        "quantity > 0",
    )
    op.create_check_constraint(
        "ck_coin_transaction_zero_only_gift_received",
        "coin_transactions",
        "amount <> 0 OR reason = 'gift_received'",
    )
    op.create_check_constraint(
        "ck_pvp_match_not_self",
        "pvp_matches",
        "creator_id <> opponent_id OR opponent_id IS NULL",
    )
    op.create_check_constraint(
        "ck_pvp_match_status",
        "pvp_matches",
        "status IN ('open', 'active', 'declined', 'expired', 'finished', 'draw')",
    )
    op.create_check_constraint(
        "ck_game_profile_level_positive",
        "game_profiles",
        "level >= 1",
    )
    op.create_check_constraint(
        "ck_game_profile_counters_nonnegative",
        "game_profiles",
        "experience >= 0 AND games_played >= 0 AND wins >= 0 AND losses >= 0 AND draws >= 0",
    )
    op.create_check_constraint(
        "ck_shop_item_price_nonnegative",
        "shop_items",
        "price >= 0",
    )
    op.create_check_constraint(
        "ck_achievement_target_nonnegative",
        "achievements",
        "target >= 0",
    )


def downgrade() -> None:
    for name, table in (
        ("ck_achievement_target_nonnegative", "achievements"),
        ("ck_shop_item_price_nonnegative", "shop_items"),
        ("ck_game_profile_counters_nonnegative", "game_profiles"),
        ("ck_game_profile_level_positive", "game_profiles"),
        ("ck_pvp_match_status", "pvp_matches"),
        ("ck_pvp_match_not_self", "pvp_matches"),
        ("ck_coin_transaction_zero_only_gift_received", "coin_transactions"),
        ("ck_inventory_quantity_positive", "user_inventory"),
        ("ck_economy_lifetime_spent_nonnegative", "economy_accounts"),
        ("ck_economy_lifetime_earned_nonnegative", "economy_accounts"),
        ("ck_economy_daily_streak_nonnegative", "economy_accounts"),
        ("ck_economy_balance_nonnegative", "economy_accounts"),
        ("ck_community_rep_vote_not_self", "community_reputation_votes"),
        ("ck_reputation_rating_not_self", "reputation_ratings"),
    ):
        op.drop_constraint(name, table_name=table, type_="check")
