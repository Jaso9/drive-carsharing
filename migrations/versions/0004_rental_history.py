"""Preserve vehicle identity and trip endpoints."""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("rentals") as batch:
        batch.add_column(
            sa.Column("car_name_snapshot", sa.String(125), nullable=False, server_default="")
        )
        batch.add_column(
            sa.Column("plate_snapshot", sa.String(20), nullable=False, server_default="")
        )
        batch.add_column(
            sa.Column("pickup_address", sa.String(200), nullable=False, server_default="")
        )
        batch.add_column(sa.Column("finish_address", sa.String(200)))
    # Identity can be backfilled; historic endpoints cannot be reliably reconstructed.
    op.execute(
        "UPDATE rentals SET car_name_snapshot = (SELECT brand || ' ' || model FROM cars WHERE cars.id = rentals.car_id), plate_snapshot = (SELECT plate FROM cars WHERE cars.id = rentals.car_id)"
    )
    op.execute(
        "UPDATE rentals SET pickup_address = (SELECT address FROM cars WHERE cars.id = rentals.car_id) WHERE status = 'reserved'"
    )


def downgrade():
    with op.batch_alter_table("rentals") as batch:
        batch.drop_column("finish_address")
        batch.drop_column("pickup_address")
        batch.drop_column("plate_snapshot")
        batch.drop_column("car_name_snapshot")
