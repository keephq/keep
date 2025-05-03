#!/bin/bash
# This script used to create a dummy migration for e2e migration test

# Create alembic.ini
docker exec keep-keep-backend-1  cp /venv/lib/python3.11/site-packages/keep/alembic.ini ./alembic_temp.ini
docker exec keep-keep-backend-1  sed -i 's|script_location.*|script_location = /venv/lib/python3.11/site-packages/keep/api/models/db/migrations|' ./al

# Get the path to the last migration
LAST_MIGRATION=$(ls -t /venv/lib/python3.11/site-packages/keep/api/models/db/migrations/versions/*.py | head -n1)
echo "Last migration: $LAST_MIGRATION"

# Create a test migration
cd /venv/lib/python3.11/site-packages/keep/api/models/db/
alembic -c /home/app/alembic_temp.ini revision -m "test_dummy_migration"

# Get the path to the created migration
NEW_MIGRATION=$(ls -t migrations/versions/*.py | head -n1)

# Modify the migration, adding empty upgrade and downgrade operations
cat > "$NEW_MIGRATION" << EOF
"""test_dummy_migration

Revision ID: $(basename "$NEW_MIGRATION" .py)
Revises: $(basename "$LAST_MIGRATION" .py)
Create Date: $(date +"%Y-%m-%d %H:%M:%S")

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '$(basename "$NEW_MIGRATION" .py)'
down_revision = '$(basename "$LAST_MIGRATION" .py)'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Empty upgrade operation
    pass

def downgrade() -> None:
    # Empty downgrade operation
    pass
EOF

echo "Test migration successfully created: $NEW_MIGRATION"

alembic -c /home/app/alembic_temp.ini upgrade head

echo "Test migration applied"
