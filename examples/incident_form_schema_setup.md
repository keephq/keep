# Incident Form Schema Setup Guide

This guide shows how to configure custom incident creation forms and integrate them with workflow automation for ticket creation.

## Overview

The incident form schema system allows you to:
1. Define custom fields that appear when creating incidents
2. Collect structured data during incident creation
3. Use that data in workflows for automatic ticket creation
4. Create consistent incident documentation

## Step 1: Configure Form Schema

Create a form schema via the API to define custom fields:

```bash
curl -X POST "${KEEP_API_URL}/incidents/form-schema" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Standard Incident Form",
    "description": "Collect essential information for incident response",
    "is_active": true,
    "fields": [
      {
        "name": "project_key",
        "label": "Jira Project",
        "type": "select",
        "description": "Select the Jira project for ticket creation",
        "required": true,
        "options": ["INCIDENT", "SUPPORT", "DEVOPS", "SECURITY"]
      },
      {
        "name": "priority",
        "label": "Business Priority",
        "type": "select",
        "description": "Business impact priority",
        "required": true,
        "options": ["Critical", "High", "Medium", "Low"],
        "default_value": "Medium"
      },
      {
        "name": "business_impact",
        "label": "Business Impact",
        "type": "textarea",
        "description": "Describe the business impact of this incident",
        "required": true,
        "max_length": 500
      },
      {
        "name": "affected_systems",
        "label": "Affected Systems",
        "type": "text",
        "description": "List the systems affected by this incident",
        "required": false,
        "placeholder": "e.g., API Gateway, Database, Frontend"
      },
      {
        "name": "create_ticket",
        "label": "Create Jira Ticket",
        "type": "checkbox",
        "description": "Automatically create a Jira ticket for this incident",
        "required": false,
        "default_value": true
      },
      {
        "name": "resolution_date",
        "label": "Expected Resolution Date",
        "type": "date",
        "description": "When do you expect this incident to be resolved?",
        "required": false
      },
      {
        "name": "escalation_level",
        "label": "Escalation Level",
        "type": "number",
        "description": "Escalation level (1-5)",
        "required": false,
        "min_value": 1,
        "max_value": 5,
        "default_value": 1
      }
    ]
  }'
```

## Step 2: Create Workflow for Ticket Creation

Create a workflow that triggers on incident creation and uses the enrichment data:

```yaml
workflow:
  id: jira-incident-automation
  description: Auto-create Jira tickets from incident enrichments
  triggers:
    - type: incident
      filters:
        - key: status
          value: firing
        - key: enrichments.create_ticket
          value: true

  steps:
    - name: create-jira-ticket
      provider:
        type: jira
        with:
          project_key: "{{ incident.enrichments.project_key }}"
          summary: "{{ incident.user_generated_name }}"
          description: |
            **Incident Details:**
            - ID: {{ incident.id }}
            - Status: {{ incident.status }}
            - Severity: {{ incident.severity }}
            - Business Impact: {{ incident.enrichments.business_impact }}
            - Affected Systems: {{ incident.enrichments.affected_systems }}
            - Expected Resolution: {{ incident.enrichments.resolution_date }}
            
            **Incident Summary:**
            {{ incident.user_summary }}
            
            **Keep URL:** {{ keep_base_url }}/incidents/{{ incident.id }}
          
          issue_type: "Bug"
          labels: ["keep-incident", "auto-created"]
          custom_fields:
            priority:
              name: "{{ incident.enrichments.priority }}"

    - name: enrich-incident
      provider:
        type: keep
        with:
          enrichments:
            ticket_id: "{{ steps.create-jira-ticket.results.issue.key }}"
            ticket_url: "{{ steps.create-jira-ticket.results.ticket_url }}"
```

## Step 3: Test the Integration

1. Create a new incident through the Keep UI
2. Fill in the custom form fields
3. Check that the workflow triggers and creates a Jira ticket
4. Verify the ticket contains the enrichment data
5. Confirm the incident is enriched with ticket information
6. Check that the incident table shows a clickable ticket link in the "Ticket" column

## Available Field Types

The system supports these field types:

### Text Fields
```json
{
  "name": "field_name",
  "label": "Display Label",
  "type": "text",
  "placeholder": "Enter text here",
  "max_length": 100,
  "required": true
}
```

### Textarea Fields
```json
{
  "name": "description",
  "label": "Description",
  "type": "textarea",
  "placeholder": "Enter detailed description",
  "max_length": 500,
  "required": false
}
```

### Select Dropdowns
```json
{
  "name": "priority",
  "label": "Priority",
  "type": "select",
  "options": ["High", "Medium", "Low"],
  "default_value": "Medium",
  "required": true
}
```

### Radio Buttons
```json
{
  "name": "severity",
  "label": "Severity Level",
  "type": "radio",
  "options": ["Critical", "Major", "Minor"],
  "required": true
}
```

### Checkboxes
```json
{
  "name": "send_notifications",
  "label": "Send Notifications",
  "type": "checkbox",
  "description": "Notify stakeholders about this incident",
  "default_value": true
}
```

### Number Fields
```json
{
  "name": "affected_users",
  "label": "Affected Users",
  "type": "number",
  "min_value": 0,
  "max_value": 10000,
  "placeholder": "Number of affected users"
}
```

### Date Fields
```json
{
  "name": "target_resolution",
  "label": "Target Resolution Date",
  "type": "date",
  "required": false
}
```

## Workflow Integration Patterns

### Conditional Ticket Creation
```yaml
- name: create-ticket
  condition: "{{ incident.enrichments.create_ticket == true }}"
  provider:
    type: jira
    # ... ticket creation config
```

### Dynamic Project Selection
```yaml
- name: create-ticket
  provider:
    type: jira
    with:
      project_key: "{{ incident.enrichments.project_key or 'DEFAULT' }}"
      # ... rest of config
```

### Priority Mapping
```yaml
- name: create-ticket
  provider:
    type: jira
    with:
      custom_fields:
        priority:
          name: "{{ incident.enrichments.priority }}"
      # ... rest of config
```

## Management Commands

### View Current Schema
```bash
curl "${KEEP_API_URL}/incidents/form-schema"
```

### Update Schema
```bash
curl -X POST "${KEEP_API_URL}/incidents/form-schema" \
  -H "Content-Type: application/json" \
  -d '{ ... updated schema ... }'
```

### Delete Schema
```bash
curl -X DELETE "${KEEP_API_URL}/incidents/form-schema"
```

## Best Practices

1. **Keep forms simple**: Only collect essential information to avoid form fatigue
2. **Use sensible defaults**: Pre-populate common values to speed up incident creation
3. **Validate in workflows**: Add conditions to handle missing or invalid enrichment data
4. **Test thoroughly**: Verify workflows work with different enrichment combinations
5. **Document field purposes**: Use clear labels and descriptions for all fields
6. **Regular cleanup**: Remove unused enrichment fields to keep the schema clean

## Ticket Link Display

When workflows enrich incidents with ticket information, the incidents table automatically displays clickable ticket links:

- **Required enrichments**: `ticket_url` (the clickable link)
- **Optional enrichments**: `ticket_id` (custom display text)
- **Automatic fallback**: If only `ticket_url` is provided, the last segment of the URL path is used as display text
- **Link behavior**: Opens ticket in new tab with external link icon

Example enrichment from workflow:
```yaml
enrichments:
  ticket_id: "PROJ-123"           # Display text
  ticket_url: "https://company.atlassian.net/browse/PROJ-123"  # Link URL
```

## Troubleshooting

### Form Not Appearing
- Check that the form schema is active: `is_active: true`
- Verify the schema exists via the API
- Check browser console for errors

### Workflow Not Triggering
- Ensure the incident has enrichments: `incident.enrichments | length > 0`
- Check workflow filters match the enrichment data
- Review workflow execution logs

### Missing Enrichment Data
- Verify field names match between form schema and workflow
- Check that required fields are filled before incident creation
- Use default values in workflows: `{{ incident.enrichments.field_name or 'default' }}`

### Ticket Links Not Showing
- Verify the incident has `ticket_url` enrichment
- Check that the URL starts with `http` or `https`
- Ensure the workflow properly enriches the incident with ticket information