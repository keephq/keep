import { extractWorkflowYamlDependencies } from "../extractWorkflowYamlDependencies";

describe("extractWorkflowYamlDependencies", () => {
  it("should extract basic dependencies", () => {
    const yaml = `
      workflow:
        steps:
          - name: step1
            provider:
              config: "{{ providers.http }}"
              with:
                token: "{{ secrets.API_KEY }}"
        actions:
          - name: action1
            provider:
              with:
                message: "{{ inputs.message }}"
    `;

    const dependencies = extractWorkflowYamlDependencies(yaml);

    expect(dependencies).toEqual({
      providers: ["http"],
      secrets: ["API_KEY"],
      inputs: ["message"],
      alert: [],
      incident: [],
    });
  });

  it("should extract nested alert properties", () => {
    const yaml = `
      workflow:
        steps:
          - name: step1
            provider:
              with:
                message: "Alert severity: {{ alert.labels.severity }}"
                summary: "Alert from {{ alert.labels.instance }} in {{ alert.labels.job }}"
                description: "Value: {{ alert.value }}"
    `;

    const dependencies = extractWorkflowYamlDependencies(yaml);

    expect(dependencies).toEqual({
      providers: [],
      secrets: [],
      inputs: [],
      alert: ["labels.severity", "labels.instance", "labels.job", "value"],
      incident: [],
    });
  });

  it("should extract nested incident properties", () => {
    const yaml = `
      workflow:
        steps:
          - name: step1
            provider:
              with:
                message: "Incident status: {{ incident.status }}"
                details: "Created by {{ incident.created_by.name }} ({{ incident.created_by.email }})"
                severity: "{{ incident.custom_fields.severity }}"
    `;

    const dependencies = extractWorkflowYamlDependencies(yaml);

    expect(dependencies).toEqual({
      providers: [],
      secrets: [],
      inputs: [],
      alert: [],
      incident: [
        "status",
        "created_by.name",
        "created_by.email",
        "custom_fields.severity",
      ],
    });
  });

  it("should extract multiple dependencies of the same type", () => {
    const yaml = `
      workflow:
        steps:
          - name: step1
            provider:
              config: "{{ providers.http }}"
          - name: step2
            provider:
              config: "{{ providers.slack }}"
              with:
                token: "{{ secrets.SLACK_TOKEN }}"
                api_key: "{{ secrets.API_KEY }}"
    `;

    const dependencies = extractWorkflowYamlDependencies(yaml);

    expect(dependencies).toEqual({
      providers: ["http", "slack"],
      secrets: ["SLACK_TOKEN", "API_KEY"],
      inputs: [],
      alert: [],
      incident: [],
    });
  });

  it("should handle complex nested structure with mixed dependencies", () => {
    const yaml = `
      workflow:
        steps:
          - name: alert-step
            if: "{{ alert.labels.severity }} == 'critical'"
            provider:
              config: "{{ providers.http }}"
              with:
                url: "https://api.example.com/incidents"
                headers:
                  Authorization: "Bearer {{ secrets.API_KEY }}"
                body: |
                  {
                    "alert": "{{ alert.name }}",
                    "severity": "{{ alert.labels.severity }}",
                    "instance": "{{ alert.labels.instance }}",
                    "value": "{{ alert.value }}",
                    "message": "{{ inputs.custom_message }}",
                    "incident_id": "{{ incident.id }}",
                    "owner": "{{ incident.assigned_to.name }}"
                  }
    `;

    const dependencies = extractWorkflowYamlDependencies(yaml);

    expect(dependencies).toEqual({
      providers: ["http"],
      secrets: ["API_KEY"],
      inputs: ["custom_message"],
      alert: ["labels.severity", "name", "labels.instance", "value"],
      incident: ["id", "assigned_to.name"],
    });
  });

  it("should deduplicate repeated dependencies", () => {
    const yaml = `
      workflow:
        steps:
          - name: step1
            provider:
              with:
                message: "Alert {{ alert.labels.severity }} from {{ alert.labels.severity }}"
                token: "{{ secrets.TOKEN }}"
        actions:
          - name: action1
            provider:
              config: "{{ providers.slack }}"
              with:
                token: "{{ secrets.TOKEN }}"
    `;

    const dependencies = extractWorkflowYamlDependencies(yaml);

    expect(dependencies).toEqual({
      providers: ["slack"],
      secrets: ["TOKEN"],
      inputs: [],
      alert: ["labels.severity"],
      incident: [],
    });
  });
});
