"""
Integration tests for IncidentFormSchema with PydanticListType.
Tests the full database persistence flow.
"""

import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from keep.api.models.db.incident_form_schema import IncidentFormSchema
from keep.api.models.incident_form_schema import FormFieldSchema, FieldType


@pytest.fixture
def db_session():
    """Create a test database session"""
    # Create in-memory SQLite database for testing
    engine = create_engine("sqlite:///:memory:")
    
    # Create all tables except those with foreign keys we don't need
    from sqlalchemy import MetaData, Table
    metadata = MetaData()
    
    # Create only the incidentformschema table
    incident_form_schema_table = Table(
        'incidentformschema',
        metadata,
        *[c.copy() for c in IncidentFormSchema.__table__.columns if c.name != 'tenant_id']
    )
    
    # Add tenant_id without foreign key for testing
    from sqlalchemy import Column, String
    incident_form_schema_table.append_column(
        Column('tenant_id', String, nullable=False)
    )
    
    metadata.create_all(engine)
    
    with Session(engine) as session:
        yield session


class TestIncidentFormSchemaPersistence:
    """Test database persistence of incident form schemas"""
    
    def test_create_and_retrieve_schema(self, db_session):
        """Test creating a schema with Pydantic fields and retrieving it"""
        # Arrange
        test_fields = [
            FormFieldSchema(
                name="project_key",
                label="Jira Project",
                type=FieldType.SELECT,
                description="Target project",
                required=True,
                options=["OPS", "DEV", "SUPPORT"],
                default_value="OPS"
            ),
            FormFieldSchema(
                name="priority",
                label="Priority",
                type=FieldType.SELECT,
                options=["High", "Medium", "Low"],
                default_value="Medium"
            ),
            FormFieldSchema(
                name="urgent",
                label="Urgent",
                type=FieldType.CHECKBOX,
                default_value=False
            )
        ]
        
        schema = IncidentFormSchema(
            tenant_id="test-tenant",
            name="Test Schema",
            description="Test description",
            fields=test_fields,
            created_by="test@example.com"
        )
        
        # Act - Save
        db_session.add(schema)
        db_session.commit()
        schema_id = schema.id
        
        # Clear session to force reload from database
        db_session.expunge_all()
        
        # Act - Retrieve
        loaded_schema = db_session.query(IncidentFormSchema).filter_by(id=schema_id).first()
        
        # Assert
        assert loaded_schema is not None
        assert loaded_schema.name == "Test Schema"
        assert len(loaded_schema.fields) == 3
        
        # Verify fields are FormFieldSchema instances with correct data
        for i, field in enumerate(loaded_schema.fields):
            assert isinstance(field, FormFieldSchema)
            
        field0 = loaded_schema.fields[0]
        assert field0.name == "project_key"
        assert field0.type == FieldType.SELECT
        assert field0.options == ["OPS", "DEV", "SUPPORT"]
        assert field0.required is True
        
        field1 = loaded_schema.fields[1]
        assert field1.name == "priority"
        assert field1.default_value == "Medium"
        
        field2 = loaded_schema.fields[2]
        assert field2.name == "urgent"
        assert field2.type == FieldType.CHECKBOX
    
    def test_update_schema_fields(self, db_session):
        """Test updating schema fields"""
        # Arrange - Create initial schema
        initial_fields = [
            FormFieldSchema(
                name="field1",
                label="Field 1",
                type=FieldType.TEXT
            )
        ]
        
        schema = IncidentFormSchema(
            tenant_id="test-tenant",
            name="Update Test",
            fields=initial_fields,
            created_by="test@example.com"
        )
        
        db_session.add(schema)
        db_session.commit()
        schema_id = schema.id
        
        # Act - Update fields
        schema.fields = [
            FormFieldSchema(
                name="field1_updated",
                label="Updated Field 1",
                type=FieldType.TEXTAREA,
                max_length=500
            ),
            FormFieldSchema(
                name="field2_new",
                label="New Field 2",
                type=FieldType.NUMBER,
                min_value=0,
                max_value=100
            )
        ]
        db_session.commit()
        
        # Clear session to force reload
        db_session.expunge_all()
        
        # Assert
        updated_schema = db_session.query(IncidentFormSchema).filter_by(id=schema_id).first()
        assert len(updated_schema.fields) == 2
        
        assert updated_schema.fields[0].name == "field1_updated"
        assert updated_schema.fields[0].type == FieldType.TEXTAREA
        assert updated_schema.fields[0].max_length == 500
        
        assert updated_schema.fields[1].name == "field2_new"
        assert updated_schema.fields[1].type == FieldType.NUMBER
        assert updated_schema.fields[1].min_value == 0
        assert updated_schema.fields[1].max_value == 100
    
    def test_empty_fields_list(self, db_session):
        """Test schema with empty fields list"""
        # Arrange
        schema = IncidentFormSchema(
            tenant_id="test-tenant",
            name="Empty Fields Test",
            fields=[],
            created_by="test@example.com"
        )
        
        # Act
        db_session.add(schema)
        db_session.commit()
        schema_id = schema.id
        
        db_session.expunge_all()
        loaded_schema = db_session.query(IncidentFormSchema).filter_by(id=schema_id).first()
        
        # Assert
        assert loaded_schema is not None
        assert loaded_schema.fields == []
    
    def test_field_modification_persists(self, db_session):
        """Test that modifications to individual fields persist"""
        # Arrange
        schema = IncidentFormSchema(
            tenant_id="test-tenant",
            name="Field Modification Test",
            fields=[
                FormFieldSchema(
                    name="modifiable",
                    label="Modifiable Field",
                    type=FieldType.TEXT,
                    required=False
                )
            ],
            created_by="test@example.com"
        )
        
        db_session.add(schema)
        db_session.commit()
        schema_id = schema.id
        
        # Act - Modify field by creating a new list with modified field
        # This is necessary for SQLAlchemy to detect changes in JSON columns
        modified_field = FormFieldSchema(
            name="modifiable",
            label="Modifiable Field",
            type=FieldType.TEXT,
            required=True,  # Changed from False
            placeholder="Enter text here"  # Added
        )
        schema.fields = [modified_field]  # Reassign to trigger SQLAlchemy change detection
        db_session.commit()
        
        # Clear and reload
        db_session.expunge_all()
        loaded_schema = db_session.query(IncidentFormSchema).filter_by(id=schema_id).first()
        
        # Assert
        assert loaded_schema.fields[0].required is True
        assert loaded_schema.fields[0].placeholder == "Enter text here"