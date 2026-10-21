"""Add optional ratings and personal notes."""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("books", sa.Column("rating", sa.SmallInteger(), nullable=True))
    op.add_column("books", sa.Column("notes", sa.Text(), nullable=False, server_default=""))
    op.create_check_constraint("books_rating_valid", "books", "rating BETWEEN 1 AND 5")
    op.create_check_constraint("books_notes_length", "books", "char_length(notes) <= 2000")


def downgrade():
    op.drop_constraint("books_notes_length", "books", type_="check")
    op.drop_constraint("books_rating_valid", "books", type_="check")
    op.drop_column("books", "notes")
    op.drop_column("books", "rating")
