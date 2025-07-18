"""
Unit tests for PydanticListType custom SQLAlchemy type.
"""

import pytest
from keep.api.models.db.types import PydanticListType
from keep.api.models.incident_form_schema import FormFieldSchema, FieldType


class TestPydanticListType:
    """Test suite for PydanticListType"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.pydantic_type = PydanticListType(FormFieldSchema)
        self.test_fields = [
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
                name="urgent",
                label="Urgent",
                type=FieldType.CHECKBOX,
                default_value=False
            )
        ]
    
    def test_process_bind_param_with_pydantic_models(self):
        """Test serialization of Pydantic models to dicts"""
        # Act
        result = self.pydantic_type.process_bind_param(self.test_fields, None)
        
        # Assert
        assert isinstance(result, list)
        assert len(result) == 2
        
        # Check all items are dicts
        for item in result:
            assert isinstance(item, dict)
        
        # Verify data preservation
        assert result[0]["name"] == "project_key"
        assert result[0]["type"] == "select"  # Enum converted to string
        assert result[0]["options"] == ["OPS", "DEV", "SUPPORT"]
        assert result[0]["required"] is True
        
        assert result[1]["name"] == "urgent"
        assert result[1]["type"] == "checkbox"
        assert result[1]["default_value"] is False
    
    def test_process_bind_param_with_dicts(self):
        """Test serialization when input is already dicts"""
        # Arrange
        dict_fields = [
            {"name": "field1", "label": "Field 1", "type": "text"},
            {"name": "field2", "label": "Field 2", "type": "number"}
        ]
        
        # Act
        result = self.pydantic_type.process_bind_param(dict_fields, None)
        
        # Assert
        assert result == dict_fields  # Should pass through unchanged
    
    def test_process_bind_param_with_none(self):
        """Test serialization with None value"""
        # Act
        result = self.pydantic_type.process_bind_param(None, None)
        
        # Assert
        assert result is None
    
    def test_process_result_value_with_valid_dicts(self):
        """Test deserialization of valid dicts to Pydantic models"""
        # Arrange
        dict_fields = [
            {
                "name": "project_key",
                "label": "Jira Project",
                "type": "select",
                "description": "Target project",
                "required": True,
                "options": ["OPS", "DEV", "SUPPORT"],
                "default_value": "OPS"
            },
            {
                "name": "urgent",
                "label": "Urgent",
                "type": "checkbox",
                "default_value": False
            }
        ]
        
        # Act
        result = self.pydantic_type.process_result_value(dict_fields, None)
        
        # Assert
        assert isinstance(result, list)
        assert len(result) == 2
        
        # Check all items are FormFieldSchema instances
        for item in result:
            assert isinstance(item, FormFieldSchema)
        
        # Verify data preservation
        assert result[0].name == "project_key"
        assert result[0].type == FieldType.SELECT
        assert result[0].options == ["OPS", "DEV", "SUPPORT"]
        assert result[0].required is True
        
        assert result[1].name == "urgent"
        assert result[1].type == FieldType.CHECKBOX
        assert result[1].default_value is False
    
    def test_process_result_value_with_invalid_dicts(self):
        """Test deserialization with invalid data preserves dicts"""
        # Arrange
        mixed_data = [
            {"name": "valid_field", "label": "Valid", "type": "text"},
            {"invalid": "missing required fields"},  # Invalid - missing required fields
            {"name": "another_valid", "label": "Another", "type": "checkbox"}
        ]
        
        # Act
        result = self.pydantic_type.process_result_value(mixed_data, None)
        
        # Assert
        assert len(result) == 3
        assert isinstance(result[0], FormFieldSchema)  # Valid data converted
        assert isinstance(result[1], dict)  # Invalid data preserved as dict
        assert isinstance(result[2], FormFieldSchema)  # Valid data converted
        
        # Verify the invalid dict is unchanged
        assert result[1] == {"invalid": "missing required fields"}
    
    def test_process_result_value_with_none(self):
        """Test deserialization with None value"""
        # Act
        result = self.pydantic_type.process_result_value(None, None)
        
        # Assert
        assert result is None
    
    def test_process_result_value_with_already_pydantic(self):
        """Test deserialization when data is already Pydantic models"""
        # Act
        result = self.pydantic_type.process_result_value(self.test_fields, None)
        
        # Assert
        assert result == self.test_fields  # Should pass through unchanged
    
    def test_roundtrip_conversion(self):
        """Test full roundtrip: Pydantic -> dict -> Pydantic"""
        # Act
        serialized = self.pydantic_type.process_bind_param(self.test_fields, None)
        deserialized = self.pydantic_type.process_result_value(serialized, None)
        
        # Assert
        assert len(deserialized) == len(self.test_fields)
        for original, restored in zip(self.test_fields, deserialized):
            assert restored.name == original.name
            assert restored.label == original.label
            assert restored.type == original.type
            assert restored.required == original.required
            assert restored.default_value == original.default_value
            # Note: Can't use == directly due to how Pydantic handles equality
    
    def test_cache_ok_is_true(self):
        """Test that the type is marked as cache-safe"""
        assert PydanticListType.cache_ok is True