"""
Incident Form Schema models for dynamic incident creation forms.

This module defines the models for creating custom form schemas that allow
tenants to define additional fields during incident creation. These fields
become incident enrichments and can be used by workflows.
"""

from datetime import datetime
from enum import Enum
from typing import Any, List, Optional, Union

from pydantic import BaseModel, Field, validator


class FieldType(str, Enum):
    """Supported form field types"""
    TEXT = "text"
    TEXTAREA = "textarea"
    SELECT = "select"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    NUMBER = "number"
    DATE = "date"


class FormFieldSchema(BaseModel):
    """Defines a single form field for incident creation"""
    
    name: str = Field(
        description="Field name (becomes enrichment key)",
        regex=r"^[a-zA-Z][a-zA-Z0-9_]*$",  # Valid identifier
        min_length=1,
        max_length=50
    )
    label: str = Field(
        description="Display label for the field",
        min_length=1,
        max_length=100
    )
    type: FieldType = Field(description="Field input type")
    description: Optional[str] = Field(
        None,
        description="Help text for the field",
        max_length=500
    )
    required: bool = Field(False, description="Whether field is required")
    
    # For select/radio fields
    options: Optional[List[str]] = Field(
        None,
        description="Available options for select/radio fields",
        min_items=1,
        max_items=50
    )
    
    default_value: Optional[Any] = Field(None, description="Default value")
    
    # For text/textarea fields
    placeholder: Optional[str] = Field(
        None,
        description="Placeholder text",
        max_length=200
    )
    max_length: Optional[int] = Field(
        None,
        description="Maximum character length",
        ge=1,
        le=10000
    )
    
    # For number fields
    min_value: Optional[float] = Field(None, description="Minimum numeric value")
    max_value: Optional[float] = Field(None, description="Maximum numeric value")
    
    @validator('options')
    def validate_options_for_type(cls, v, values):
        """Validate that options are provided for select/radio fields"""
        field_type = values.get('type')
        if field_type in [FieldType.SELECT, FieldType.RADIO]:
            if not v or len(v) == 0:
                raise ValueError(f"Options are required for {field_type} fields")
            if len(set(v)) != len(v):
                raise ValueError("Options must be unique")
        elif field_type not in [FieldType.SELECT, FieldType.RADIO] and v is not None:
            raise ValueError(f"Options are not allowed for {field_type} fields")
        return v
    
    @validator('default_value')
    def validate_default_value_type(cls, v, values):
        """Validate default value matches field type"""
        field_type = values.get('type')
        options = values.get('options', [])
        
        if v is None:
            return v
            
        if field_type == FieldType.CHECKBOX:
            if not isinstance(v, bool):
                raise ValueError("Default value for checkbox must be boolean")
        elif field_type == FieldType.NUMBER:
            if not isinstance(v, (int, float)):
                raise ValueError("Default value for number must be numeric")
        elif field_type in [FieldType.SELECT, FieldType.RADIO]:
            if v not in options:
                raise ValueError("Default value must be one of the available options")
        elif field_type in [FieldType.TEXT, FieldType.TEXTAREA]:
            if not isinstance(v, str):
                raise ValueError("Default value for text fields must be string")
        
        return v
    
    @validator('max_value')
    def validate_min_max_values(cls, v, values):
        """Validate min_value <= max_value"""
        min_value = values.get('min_value')
        if min_value is not None and v is not None and min_value > v:
            raise ValueError("min_value must be less than or equal to max_value")
        return v

    class Config:
        schema_extra = {
            "examples": [
                {
                    "name": "target_project",
                    "label": "Jira Project",
                    "type": "select",
                    "description": "Target Jira project for ticket creation",
                    "required": True,
                    "options": ["OPS", "SUPPORT", "ENGINEERING"],
                    "default_value": "OPS"
                },
                {
                    "name": "urgent",
                    "label": "Urgent Issue",
                    "type": "checkbox",
                    "description": "Requires immediate attention",
                    "default_value": False
                },
                {
                    "name": "business_impact",
                    "label": "Business Impact",
                    "type": "textarea",
                    "placeholder": "Describe the business impact...",
                    "max_length": 500
                }
            ]
        }


class IncidentFormSchemaDto(BaseModel):
    """DTO for incident form schema operations"""
    
    schema_id: Optional[str] = Field(
        None,
        description="Optional schema ID for updates. If provided, updates existing schema. If not, creates new."
    )
    name: str = Field(
        description="Human-readable schema name",
        min_length=1,
        max_length=100
    )
    description: Optional[str] = Field(
        None,
        description="Schema description",
        max_length=500
    )
    fields: List[FormFieldSchema] = Field(
        description="Form fields definition",
        min_items=0,
        max_items=20  # Reasonable limit for form complexity
    )
    is_active: bool = Field(True, description="Whether schema is active")
    
    @validator('fields')
    def validate_unique_field_names(cls, v):
        """Ensure field names are unique"""
        names = [field.name for field in v]
        if len(names) != len(set(names)):
            raise ValueError("Field names must be unique")
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "name": "ACME Incident Form",
                "description": "Custom fields for incident creation with ticketing integration",
                "fields": [
                    {
                        "name": "target_project",
                        "label": "Jira Project",
                        "type": "select",
                        "description": "Target Jira project for ticket creation",
                        "required": True,
                        "options": ["OPS", "SUPPORT", "ENGINEERING", "INFRASTRUCTURE"],
                        "default_value": "OPS"
                    },
                    {
                        "name": "priority",
                        "label": "Priority Level",
                        "type": "select",
                        "options": ["Highest", "High", "Medium", "Low", "Lowest"],
                        "default_value": "Medium"
                    },
                    {
                        "name": "urgent",
                        "label": "Urgent Issue",
                        "type": "checkbox",
                        "description": "Requires immediate attention",
                        "default_value": False
                    }
                ],
                "is_active": True
            }
        }


class IncidentFormSchemaResponse(IncidentFormSchemaDto):
    """Response model including metadata"""
    
    id: str = Field(description="Unique identifier for the schema")
    tenant_id: str = Field(description="Tenant this schema belongs to")
    created_by: str = Field(description="User who created the schema")
    created_at: datetime = Field(description="When schema was created")
    updated_at: datetime = Field(description="When schema was last updated")