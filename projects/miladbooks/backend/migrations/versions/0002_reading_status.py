"""Track reading progress; existing books start on the to-read shelf."""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("books", sa.Column("status", sa.String(16), nullable=False, server_default="to_read"))
    op.create_check_constraint("books_status_valid", "books", "status IN ('to_read', 'reading', 'finished')")
    op.create_index("ix_books_status", "books", ["status"])


def downgrade():
    op.drop_index("ix_books_status", table_name="books")
    op.drop_constraint("books_status_valid", "books", type_="check")
    op.drop_column("books", "status")
