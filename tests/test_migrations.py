import pytest

from keep.api.core.db_on_start import migrate_db, get_current_revision

revision1 = """
from alembic import op
import sqlalchemy as sa

# Revision identifiers
revision = '202305010001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'users',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('email', sa.String(length=255), nullable=False, unique=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now(), nullable=False)
    )

def downgrade():
    op.drop_table('users')
"""

revision2 = """
from alembic import op
import sqlalchemy as sa

# Revision identifiers
revision = '202305010002'
down_revision = '202305010001'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('users', sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'))

def downgrade():
    op.drop_column('users', 'is_active')
"""

import os
import shutil
import tempfile

from alembic.config import Config

def test_db_migrations():
    # Create a temporary directory to act as the Alembic environment
    with tempfile.TemporaryDirectory() as temp_dir:
        os.environ["SECRET_MANAGER_DIRECTORY"] = os.path.join(temp_dir, "state")
        shutil.copytree("./tests/migrations", os.path.join(temp_dir, "migrations"))
        alembic_ini_path = os.path.join(temp_dir, "migrations", "alembic.ini")
        migrations_path = os.path.join(temp_dir, "migrations")

        alembic_cfg = Config(alembic_ini_path)
        alembic_cfg.set_main_option("script_location", migrations_path)

        current_revision = get_current_revision()

        assert current_revision is None
        os.mkdir(os.path.join(temp_dir, "migrations", "versions"))
        # Test startup revision
        with open(os.path.join(temp_dir, "migrations", "versions", "revision1.py"), "w") as f:
            f.write(revision1)

        migrate_db(alembic_ini_path, migrations_path)
        assert get_current_revision() == "202305010001"

        # Test upgrade revision
        with open(os.path.join(temp_dir, "migrations", "versions", "revision2.py"), "w") as f:
            f.write(revision2)

        migrate_db(alembic_ini_path, migrations_path)
        assert get_current_revision() == "202305010002"

        # Test downgrade revision
        os.remove(os.path.join(temp_dir, "migrations", "versions", "revision2.py"))
        # Test downgrade not allowed when ALLOW_DB_DOWNGRADE is not set
        with pytest.raises(RuntimeError):
            migrate_db(alembic_ini_path, migrations_path)

        os.environ["ALLOW_DB_DOWNGRADE"] = "true"
        migrate_db(alembic_ini_path, migrations_path)

        assert get_current_revision() == "202305010001"