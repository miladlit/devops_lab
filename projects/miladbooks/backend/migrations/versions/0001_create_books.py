"""Create books table."""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "books",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("author", sa.String(255), nullable=False),
        sa.CheckConstraint("length(trim(title)) > 0", name="books_title_nonempty"),
        sa.CheckConstraint("length(trim(author)) > 0", name="books_author_nonempty"),
    )


def downgrade():
    op.drop_table("books")
