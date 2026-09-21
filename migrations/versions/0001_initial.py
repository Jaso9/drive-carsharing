"""Initial carsharing schema."""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("password_hash", sa.String, nullable=False),
        sa.Column("is_admin", sa.Boolean, nullable=False),
    )
    op.create_table(
        "cars",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("brand", sa.String(60), nullable=False),
        sa.Column("model", sa.String(60), nullable=False),
        sa.Column("plate", sa.String(20), nullable=False, unique=True),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("address", sa.String(200), nullable=False),
        sa.Column("fuel", sa.Integer, nullable=False),
        sa.Column("rate_kopecks", sa.Integer, nullable=False),
        sa.Column("status", sa.String, nullable=False),
        sa.CheckConstraint("rate_kopecks > 0"),
        sa.CheckConstraint("fuel BETWEEN 0 AND 100"),
        sa.CheckConstraint("status IN ('available','reserved','rented','maintenance')"),
    )
    op.create_table(
        "rentals",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("car_id", sa.Integer, sa.ForeignKey("cars.id"), nullable=False),
        sa.Column("status", sa.String, nullable=False),
        sa.Column("rate_kopecks", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("started_at", sa.DateTime),
        sa.Column("finished_at", sa.DateTime),
        sa.Column("total_kopecks", sa.Integer, nullable=False),
        sa.CheckConstraint("status IN ('reserved','active','completed','cancelled')"),
    )
    for name in ["user", "car"]:
        op.create_index(
            f"uq_{name}_open_rental",
            "rentals",
            [f"{name}_id"],
            unique=True,
            sqlite_where=sa.text("status IN ('reserved','active')"),
            postgresql_where=sa.text("status IN ('reserved','active')"),
        )


def downgrade():
    op.drop_table("rentals")
    op.drop_table("cars")
    op.drop_table("users")
