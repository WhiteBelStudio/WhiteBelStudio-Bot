"""Add virtual coin economy and shop.

Revision ID: 0010_economy_shop
Revises: 0009_game_system
"""

from alembic import op
import sqlalchemy as sa

revision = "0010_economy_shop"
down_revision = "0009_game_system"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "economy_accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("balance", sa.Numeric(12, 1), nullable=False, server_default="0.0"),
        sa.Column("daily_streak", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_daily_claim_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lifetime_earned", sa.Numeric(14, 1), nullable=False, server_default="0.0"),
        sa.Column("lifetime_spent", sa.Numeric(14, 1), nullable=False, server_default="0.0"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_economy_account_user"),
    )
    op.create_index("ix_economy_accounts_user_id", "economy_accounts", ["user_id"])

    op.create_table(
        "shop_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("price", sa.Numeric(12, 1), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_shop_item_code"),
    )

    op.create_table(
        "user_inventory",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["item_id"], ["shop_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "item_id", name="uq_inventory_user_item"),
    )
    op.create_index("ix_user_inventory_user_id", "user_inventory", ["user_id"])

    op.create_table(
        "coin_transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 1), nullable=False),
        sa.Column("balance_after", sa.Numeric(12, 1), nullable=False),
        sa.Column("reason", sa.String(64), nullable=False),
        sa.Column("reference_user_id", sa.Integer(), nullable=True),
        sa.Column("item_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reference_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["item_id"], ["shop_items.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_coin_transactions_user_id", "coin_transactions", ["user_id"])

    items = sa.table(
        "shop_items",
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("description", sa.String()),
        sa.column("category", sa.String()),
        sa.column("price", sa.Numeric(12, 1)),
    )
    op.bulk_insert(items, [
        {"code": "title_activist", "name": "🏷️ Активист", "description": "Титул для профиля.", "category": "title", "price": 5.0},
        {"code": "title_veteran", "name": "🏷️ Ветеран", "description": "Титул для профиля.", "category": "title", "price": 15.0},
        {"code": "title_gamer", "name": "🎮 Игрок", "description": "Титул для профиля.", "category": "title", "price": 10.0},
        {"code": "title_brain", "name": "🧠 Мозг", "description": "Титул для профиля.", "category": "title", "price": 20.0},
        {"code": "boost_attempt", "name": "⚡ +1 попытка", "description": "Одноразовое игровое улучшение.", "category": "boost", "price": 2.5},
        {"code": "boost_hint", "name": "💡 Подсказка", "description": "Одноразовая подсказка для поддерживаемых игр.", "category": "boost", "price": 1.0},
        {"code": "boost_streak", "name": "🔥 Заморозка серии", "description": "Защищает игровую серию от одного пропуска.", "category": "boost", "price": 5.0},
        {"code": "gift_heart", "name": "❤️ Сердце", "description": "Виртуальный подарок участнику.", "category": "gift", "price": 0.5},
        {"code": "gift_star", "name": "⭐ Звезда", "description": "Виртуальный подарок участнику.", "category": "gift", "price": 1.0},
        {"code": "gift_fire", "name": "🔥 Огонь", "description": "Виртуальный подарок участнику.", "category": "gift", "price": 2.5},
        {"code": "gift_crown", "name": "👑 Корона", "description": "Виртуальный подарок участнику.", "category": "gift", "price": 5.0},
        {"code": "gift_diamond", "name": "💎 Алмаз", "description": "Виртуальный подарок участнику.", "category": "gift", "price": 10.0},
        {"code": "exclusive_100wins", "name": "🏆 100 побед", "description": "Эксклюзивный предмет за достижение.", "category": "exclusive", "price": 25.0},
        {"code": "exclusive_30days", "name": "🔥 30 дней активности", "description": "Эксклюзивный предмет за серию.", "category": "exclusive", "price": 30.0},
        {"code": "exclusive_500games", "name": "🎮 500 игр", "description": "Эксклюзивный предмет за игровой прогресс.", "category": "exclusive", "price": 50.0},
        {"code": "exclusive_365days", "name": "💎 365 дней", "description": "Эксклюзивный предмет за год активности.", "category": "exclusive", "price": 100.0},
    ])


def downgrade() -> None:
    op.drop_index("ix_coin_transactions_user_id", table_name="coin_transactions")
    op.drop_table("coin_transactions")
    op.drop_index("ix_user_inventory_user_id", table_name="user_inventory")
    op.drop_table("user_inventory")
    op.drop_table("shop_items")
    op.drop_index("ix_economy_accounts_user_id", table_name="economy_accounts")
    op.drop_table("economy_accounts")
