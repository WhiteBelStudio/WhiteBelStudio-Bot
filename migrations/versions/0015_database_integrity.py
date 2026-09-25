"""Enforce database-level integrity for core domains.

Revision ID: 0015_database_integrity
Revises: 0014_remove_social_system
"""

from alembic import op

revision = "0015_database_integrity"
down_revision = "0014_remove_social_system"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_reputation_rating_score",
        "reputation_ratings",
        "score BETWEEN 1 AND 5",
    )
    op.create_check_constraint(
        "ck_reputation_rating_not_self",
        "reputation_ratings",
        "rater_id <> rated_id",
    )
    op.create_check_constraint(
        "ck_community_rep_vote_score",
        "community_reputation_votes",
        "score IN (-1, 1)",
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


def downgrade() -> None:
    for name, table in (
        ("ck_pvp_match_status", "pvp_matches"),
        ("ck_pvp_match_not_self", "pvp_matches"),
        ("ck_coin_transaction_zero_only_gift_received", "coin_transactions"),
        ("ck_inventory_quantity_positive", "user_inventory"),
        ("ck_economy_lifetime_spent_nonnegative", "economy_accounts"),
        ("ck_economy_lifetime_earned_nonnegative", "economy_accounts"),
        ("ck_economy_daily_streak_nonnegative", "economy_accounts"),
        ("ck_economy_balance_nonnegative", "economy_accounts"),
        ("ck_community_rep_vote_not_self", "community_reputation_votes"),
        ("ck_community_rep_vote_score", "community_reputation_votes"),
        ("ck_reputation_rating_not_self", "reputation_ratings"),
        ("ck_reputation_rating_score", "reputation_ratings"),
    ):
        op.drop_constraint(name, table_name=table, type_="check")
