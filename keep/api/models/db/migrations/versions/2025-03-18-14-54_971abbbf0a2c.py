"""Default workflow_id=None for WorkflowExecution for test runs

Revision ID: 971abbbf0a2c
Revises: c0880e315ebe
Create Date: 2025-03-18 14:54:56.003392

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = "971abbbf0a2c"
down_revision = "c0880e315ebe"
branch_labels = None
depends_on = None



def upgrade() -> None:
    # First check if the column is nullable (for those who haven't migrated yet)
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    columns = inspector.get_columns('workflowexecution')
    workflow_id_column = next((c for c in columns if c['name'] == 'workflow_id'), None)
    
    is_nullable = workflow_id_column.get('nullable', True) if workflow_id_column else True

    # Check if the foreign key constraint exists
    foreign_keys = inspector.get_foreign_keys('workflowexecution')
    fk_names = [fk.get('name') for fk in foreign_keys]

    # First drop the foreign key constraint
    if 'workflowexecution_ibfk_2' in fk_names or any(fk.get('referred_table') == 'workflow' and 'workflow_id' in fk.get('constrained_columns', []) for fk in foreign_keys):
        with op.batch_alter_table("workflowexecution", schema=None) as batch_op:
            batch_op.drop_constraint('workflowexecution_ibfk_2', type_='foreignkey')
    
    # Update NULL values to 'test' if needed
        batch_op.drop_constraint('workflowexecution_ibfk_2', type_='foreignkey')
    
    # Update NULL values to 'test' if needed
    if is_nullable:
        op.execute("UPDATE workflowexecution SET workflow_id = 'test' WHERE workflow_id IS NULL")
    
    # Conditionally check if indexes exist before dropping
    indexes = inspector.get_indexes('workflowexecution')
    index_names = [idx['name'] for idx in indexes]
    
    with op.batch_alter_table("workflowexecution", schema=None) as batch_op:
        # Make column NOT NULL with default 'test'
        batch_op.alter_column(
            "workflow_id", 
            existing_type=mysql.VARCHAR(length=255), 
            nullable=False,
            server_default="TEST"
        )
        
        # Only drop indexes if they exist
        if "idx_status_started" in index_names:
            batch_op.drop_index("idx_status_started")
            
        if "idx_workflowexecution_workflow_tenant_started_status" in index_names:
            batch_op.drop_index("idx_workflowexecution_workflow_tenant_started_status")
        
        # Create new index (this will fail if it already exists)
        try:
            batch_op.create_index(
                "idx_workflowexecution_workflow_tenant_started_status",
                ["workflow_id", "tenant_id", "started", sa.text("status(255)")],
                unique=False,
            )
        except Exception as e:
            # Log that the index already exists, but don't fail the migration
            print(f"Note: Index creation skipped - {str(e)}")
        
    inspector = sa.inspect(connection)  # Refresh inspector to see current state
    foreign_keys = inspector.get_foreign_keys('workflowexecution')
    fk_names = [fk.get('name') for fk in foreign_keys]
    
    # Only add the constraint back if it doesn't exist
    has_workflow_fk = 'workflowexecution_ibfk_2' in fk_names or any(
        fk.get('referred_table') == 'workflow' and 'workflow_id' in fk.get('constrained_columns', []) 
        for fk in foreign_keys
    )
    
    if not has_workflow_fk:
        try:
            with op.batch_alter_table("workflowexecution", schema=None) as batch_op:
                batch_op.create_foreign_key(
                    'workflowexecution_ibfk_2',
                    'workflow',
                    ['workflow_id'],
                    ['id'],
                    ondelete='SET DEFAULT'
                )
        except Exception as e:
            print(f"Note: Foreign key creation skipped - {str(e)}")
    


def downgrade() -> None:
    # Similar defensive approach for downgrade
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    indexes = inspector.get_indexes('workflowexecution')
    index_names = [idx['name'] for idx in indexes]
    
    with op.batch_alter_table("workflowexecution", schema=None) as batch_op:
        # Only try to drop if it exists
        if "idx_workflowexecution_workflow_tenant_started_status" in index_names:
            batch_op.drop_index("idx_workflowexecution_workflow_tenant_started_status")
        
        # Recreate indexes if they don't exist
        try:
            batch_op.create_index(
                "idx_workflowexecution_workflow_tenant_started_status",
                ["workflow_id", "tenant_id", "started", "status"],
                unique=False,
                mysql_length={"status": 255},
            )
        except Exception:
            pass

        # Conditionally check if indexes exist before adding
        indexes = inspector.get_indexes('workflowexecution')
        index_names = [idx['name'] for idx in indexes]
        if "idx_status_started" not in index_names:
            try:
                batch_op.create_index(
                    "idx_status_started",
                    ["status", "started"],
                    unique=False,
                    mysql_length={"status": 255},
                )
            except Exception:
                pass
        
        # Make column nullable again
        batch_op.alter_column(
            "workflow_id", 
            existing_type=mysql.VARCHAR(length=255), 
            nullable=True,
            server_default=None
        )
    
    # Convert 'test' values back to NULL
    op.execute("UPDATE workflowexecution SET workflow_id = NULL WHERE workflow_id = 'test'")