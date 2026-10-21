"""Yearly reading goals and known completion dates."""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    # Existing completion dates are unknown; leave them unset.
    op.add_column("books", sa.Column("finished_on", sa.Date(), nullable=True))
    op.create_check_constraint("books_completion_status", "books", "finished_on IS NULL OR status = 'finished'")
    op.create_index("ix_books_finished_on", "books", ["finished_on"])
    op.create_table(
        "reading_goals",
        sa.Column("year", sa.Integer(), primary_key=True),
        sa.Column("target", sa.Integer(), nullable=False),
        sa.CheckConstraint("year BETWEEN 1900 AND 9998", name="reading_goal_year"),
        sa.CheckConstraint("target BETWEEN 1 AND 10000", name="reading_goal_target"),
    )


def downgrade():
    op.drop_table("reading_goals")
    op.drop_index("ix_books_finished_on", table_name="books")
    op.drop_constraint("books_completion_status", "books", type_="check")
    op.drop_column("books", "finished_on")
