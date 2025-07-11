# Incident-Level Ticketing Integration Design V2

## Overview

This document outlines the revised design for incident-level ticketing integration in Keep, specifically addressing GitHub issue #4981. The solution uses a standalone incident form schema system with enrichment-based workflows and streaming notifications to provide automatic ticket creation with real-time feedback.

## Problem Statement

Currently, Keep's ticketing integration only works at the alert level. The requirement is to extend this to incident level with:

1. **Automatic ticket creation** when incidents are created
2. **Project selection dropdown** for multi-project ticketing providers like Jira
3. **Popup with direct, clickable link** to newly created tickets
4. **Ticket ID column** on incidents pages with clickable links

## Architecture Decision: Standalone Form Schema + Enrichment-Based Workflows

This approach leverages Keep's existing systems with minimal new complexity:

✅ **Standalone form builder** - Single form schema per tenant for incident creation  
✅ **Uses existing enrichment system** - Form data becomes incident enrichments  
✅ **Natural workflow triggers** - `incident created` workflows process enrichments  
✅ **Generic notification system** - Reusable for any workflow results  
✅ **Flexible UI patterns** - Configurable enrichment columns work everywhere  

## Technical Design

### 1. Incident Form Schema System

#### Form Schema Models
```python
from pydantic import BaseModel, Field
from typing import List, Optional, Union, Any
from enum import Enum

class FieldType(str, Enum):
    TEXT = "text"
    TEXTAREA = "textarea" 
    SELECT = "select"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    NUMBER = "number"
    DATE = "date"

class FormFieldSchema(BaseModel):
    """Defines a single form field for incident creation"""
    name: str = Field(description="Field name (becomes enrichment key)")
    label: str = Field(description="Display label for the field")
    type: FieldType = Field(description="Field input type")
    description: Optional[str] = Field(None, description="Help text for the field")
    required: bool = Field(False, description="Whether field is required")
    default_value: Optional[Any] = Field(None, description="Default value")
    
    # For select/radio fields
    options: Optional[List[str]] = Field(None, description="Available options")
    
    # For text/textarea fields
    placeholder: Optional[str] = Field(None, description="Placeholder text")
    max_length: Optional[int] = Field(None, description="Maximum character length")
    
    # For number fields
    min_value: Optional[float] = Field(None, description="Minimum numeric value")
    max_value: Optional[float] = Field(None, description="Maximum numeric value")

class IncidentFormSchema(SQLModel, table=True):
    """Single form schema per tenant for incident creation"""
    __tablename__ = "incident_form_schema"
    
    tenant_id: str = Field(primary_key=True, foreign_key="tenant.id")
    name: str = Field(sa_column=Column(TEXT))
    description: Optional[str] = Field(sa_column=Column(TEXT))
    fields: List[FormFieldSchema] = Field(sa_column=Column(JSON))
    created_by: str = Field(sa_column=Column(TEXT))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = Field(default=True)
```

#### Example Form Schema
```json
{
  "tenant_id": "acme-corp",
  "name": "ACME Incident Form",
  "description": "Custom fields for incident creation with ticketing integration",
  "fields": [
    {
      "name": "target_project",
      "label": "Jira Project", 
      "type": "select",
      "description": "Target Jira project for ticket creation",
      "required": true,
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
      "default_value": false
    },
    {
      "name": "additional_context",
      "label": "Additional Context",
      "type": "textarea",
      "placeholder": "Any additional information for the ticket...",
      "max_length": 1000
    }
  ]
}
```

#### API Endpoints
```python
# Simple CRUD for the single schema per tenant
GET    /incidents/form-schema     # Get current form schema for tenant
POST   /incidents/form-schema     # Create/Update form schema for tenant  
DELETE /incidents/form-schema     # Remove form schema (revert to default)
```

### 2. Enhanced Incident Creation Flow

#### UI Integration
```tsx
const CreateIncidentModal = () => {
  const [formData, setFormData] = useState<IncidentFormData>({});
  const [enrichments, setEnrichments] = useState<Record<string, any>>({});
  
  const { data: formSchema } = useIncidentFormSchema();
  
  const renderFormField = (field: FormFieldSchema) => {
    switch (field.type) {
      case 'select':
        return (
          <Select
            value={enrichments[field.name] || field.default_value}
            onValueChange={(value) => setEnrichments(prev => ({ ...prev, [field.name]: value }))}
          >
            <SelectTrigger>
              <SelectValue placeholder={`Select ${field.label}`} />
            </SelectTrigger>
            <SelectContent>
              {field.options?.map(option => (
                <SelectItem key={option} value={option}>
                  {option}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        );
      
      case 'checkbox':
        return (
          <Checkbox
            checked={enrichments[field.name] || field.default_value}
            onCheckedChange={(checked) => setEnrichments(prev => ({ ...prev, [field.name]: checked }))}
          />
        );
      
      case 'textarea':
        return (
          <Textarea
            value={enrichments[field.name] || field.default_value || ''}
            onChange={(e) => setEnrichments(prev => ({ ...prev, [field.name]: e.target.value }))}
            placeholder={field.placeholder}
            maxLength={field.max_length}
          />
        );
      
      case 'text':
      default:
        return (
          <Input
            value={enrichments[field.name] || field.default_value || ''}
            onChange={(e) => setEnrichments(prev => ({ ...prev, [field.name]: e.target.value }))}
            placeholder={field.placeholder}
            maxLength={field.max_length}
          />
        );
    }
  };
  
  const handleSubmit = async () => {
    const incidentData = {
      ...formData,
      enrichments: enrichments
    };
    
    await createIncident(incidentData);
  };
  
  return (
    <Modal>
      {/* Standard incident form fields */}
      <IncidentFormFields value={formData} onChange={setFormData} />
      
      {/* Dynamic enrichment fields from form schema */}
      {formSchema?.fields && formSchema.fields.length > 0 && (
        <div className="space-y-4">
          <h3 className="text-lg font-medium">Additional Information</h3>
          {formSchema.fields.map((field) => (
            <div key={field.name} className="space-y-2">
              <Label>
                {field.label}
                {field.required && <span className="text-red-500"> *</span>}
              </Label>
              {renderFormField(field)}
              {field.description && (
                <p className="text-sm text-gray-500">{field.description}</p>
              )}
            </div>
          ))}
        </div>
      )}
      
      <Button onClick={handleSubmit}>Create Incident</Button>
    </Modal>
  );
};
```

### 3. Incident-Triggered Workflows

#### Example Jira Integration Workflow
```yaml
workflow:
  id: jira-incident-integration
  name: Create Jira Ticket for Incident
  description: Automatically creates Jira tickets when incidents are created with target_project enrichment
  triggers:
    - type: incident
      events:
        - created
      # Optional: filter to only incidents with specific enrichments
      filters:
        - key: target_project
          value: ".*"  # Any value (enrichment exists)
  actions:
    - name: create-jira-ticket
      # Only run if target_project enrichment exists
      if: "{{ has(incident.target_project) }}"
      provider:
        type: jira
        config: "{{ providers.jira }}"
        with:
          project_key: "{{ incident.target_project }}"
          issue_type: "Bug"
          priority: "{{ incident.priority | default('Medium') }}"
          summary: "{{ incident.user_generated_name }} [{{ incident.severity }}]"
          description: |
            **Incident Details:**
            - **Incident ID:** {{ incident.id }}
            - **Severity:** {{ incident.severity }}
            - **Status:** {{ incident.status }}
            - **Created:** {{ incident.creation_time }}
            - **Alerts Count:** {{ incident.alerts_count }}
            
            **Summary:**
            {{ incident.user_summary }}
            
            {% if incident.additional_context %}
            **Additional Context:**
            {{ incident.additional_context }}
            {% endif %}
            
            **Keep Incident URL:**
            {{ api_url }}/incidents/{{ incident.id }}
          
          labels:
            - "keep-incident"
            - "severity-{{ incident.severity }}"
            {% if incident.urgent %}- "urgent"{% endif %}
          
          # Enrich incident with ticket information
          enrich_incident:
            - key: ticket_type
              value: jira
            - key: ticket_id
              value: results.issue.key
            - key: ticket_url
              value: results.ticket_url
            - key: ticket_created_at
              value: "{{ now() }}"

    - name: notify-ticket-created
      # Stream notification to UI
      if: "{{ results.issue.key }}"
      provider:
        type: pusher
        config: "{{ providers.pusher }}"
        with:
          channel: "incidents-{{ incident.tenant_id }}"
          event: "ticket_created"
          data:
            incident_id: "{{ incident.id }}"
            message: "Ticket {{ results.issue.key }} created for Incident {{ incident.id }}"
            ticket_info:
              id: "{{ results.issue.key }}"
              url: "{{ results.ticket_url }}"
              provider: "jira"
            links:
              - text: "{{ results.issue.key }}"
                url: "{{ results.ticket_url }}"
                external: true
              - text: "View Incident"
                url: "/incidents/{{ incident.id }}"
                external: false
```

### 4. Smart Enrichment Columns

#### Configurable Column System
```tsx
const useEnrichmentColumns = () => {
  return [
    {
      key: 'ticket_id',
      label: 'Ticket',
      type: 'url',
      render: (value: string, enrichments: Record<string, any>) => {
        const url = enrichments.ticket_url;
        if (!value || !url) return null;
        
        return (
          <a 
            href={url} 
            target="_blank" 
            rel="noopener noreferrer"
            className="text-blue-600 hover:underline"
          >
            {value}
          </a>
        );
      }
    },
    {
      key: 'target_project',
      label: 'Project',
      type: 'badge',
      render: (value: string) => value ? <Badge variant="outline">{value}</Badge> : null
    },
    {
      key: 'priority',
      label: 'Priority',
      type: 'badge',
      render: (value: string) => {
        const colors = {
          'Highest': 'destructive',
          'High': 'destructive',
          'Medium': 'default', 
          'Low': 'secondary',
          'Lowest': 'secondary'
        };
        return value ? <Badge variant={colors[value]}>{value}</Badge> : null;
      }
    }
  ];
};
```

## Implementation Plan

### Phase 1: Form Schema System
1. ✅ Document standalone form schema approach
2. ✅ Create form field schema models and validation
3. ✅ Create incident form schema database table
4. ✅ Implement form schema API endpoints (GET/POST/DELETE)
5. ⬜ Add form schema management UI for admins

### Phase 2: Dynamic Form Rendering  
1. ⬜ Create dynamic form field rendering components
2. ⬜ Integrate form schema into Create Incident modal
3. ⬜ Add form validation and error handling
4. ⬜ Store form data as incident enrichments

### Phase 3: Notification Streaming
1. ⬜ Create notification provider for workflow results  
2. ⬜ Implement Pusher/WebSocket notification streaming
3. ⬜ Build frontend notification system with toast/popup
4. ⬜ Add support for clickable links in notifications

### Phase 4: Smart Enrichment UI
1. ⬜ Create configurable enrichment column system
2. ⬜ Implement smart URL rendering (extract ticket IDs)
3. ⬜ Add enrichment columns to incidents table
4. ⬜ Build enrichment display components

### Phase 5: Integration & Testing
1. ⬜ Create example Jira incident workflow
2. ⬜ Test end-to-end incident creation → workflow → notification flow
3. ⬜ Validate smart URL rendering with real ticket links
4. ⬜ Performance testing and optimization

## Benefits of This Approach

### Architectural Benefits
1. **Separation of Concerns**: Form schema is independent of workflows
2. **Minimal Complexity**: Uses existing enrichment and workflow systems
3. **Single Source of Truth**: One form schema per tenant
4. **Generic Patterns**: Notification streaming works for any workflow

### User Experience Benefits
1. **Admin Control**: Admins configure form fields once for their org
2. **Immediate Feedback**: Real-time notifications when tickets are created
3. **Smart Display**: URLs automatically render as meaningful links
4. **Progressive Enhancement**: Works with or without custom fields

### Technical Benefits
1. **Type Safety**: Pydantic models provide validation and type checking
2. **Extensible**: Easy to add new field types and validation rules
3. **Maintainable**: Builds on proven Keep patterns
4. **Performant**: No additional database queries for form rendering

## Example Form Schemas

### Basic Jira Integration
```json
{
  "name": "Basic Jira Integration", 
  "fields": [
    {
      "name": "target_project",
      "label": "Jira Project",
      "type": "select",
      "required": true,
      "options": ["OPS", "SUPPORT"],
      "default_value": "OPS"
    }
  ]
}
```

### Advanced Multi-Field Form
```json
{
  "name": "Advanced Incident Form",
  "fields": [
    {
      "name": "ticketing_system",
      "label": "Ticketing System", 
      "type": "radio",
      "required": true,
      "options": ["jira", "servicenow", "linear"],
      "default_value": "jira"
    },
    {
      "name": "project",
      "label": "Project/Category",
      "type": "select",
      "options": ["OPS", "SUPPORT", "ENGINEERING"],
      "default_value": "OPS"
    },
    {
      "name": "business_impact",
      "label": "Business Impact",
      "type": "textarea",
      "placeholder": "Describe the business impact...",
      "max_length": 500
    },
    {
      "name": "customer_facing",
      "label": "Customer Facing Issue",
      "type": "checkbox",
      "default_value": false
    }
  ]
}
```

## Future Enhancements

1. **Conditional Fields**: Show/hide fields based on other field values
2. **Field Dependencies**: Dynamic option lists based on other selections
3. **Custom Validation**: Field-level validation rules
4. **Field Groups**: Organize fields into collapsible sections
5. **Import/Export**: Share form schemas between tenants
6. **Field Templates**: Pre-built field configurations for common use cases