import {
  YamlWorkflowDefinitionSchema,
  getYamlWorkflowDefinitionSchema,
} from "@/entities/workflows/model/yaml.schema";
import { Provider } from "@/shared/api/providers";

describe("YamlWorkflowDefinitionSchema", () => {
  it("should validate a basic workflow definition", () => {
    const basicWorkflow = {
      workflow: {
        id: "test-workflow-id",
        steps: [
          {
            name: "test-step",
            provider: {
              type: "mock",
              config: "mock-config",
              with: {},
            },
          },
        ],
        triggers: [
          {
            type: "manual",
          },
        ],
      },
    };

    expect(() =>
      YamlWorkflowDefinitionSchema.parse(basicWorkflow)
    ).not.toThrow();
  });

  it("should validate a workflow with all optional fields", () => {
    const fullWorkflow = {
      workflow: {
        id: "test-workflow-id",
        name: "Test Workflow",
        description: "A test workflow with all fields",
        disabled: false,
        owners: ["user1", "user2"],
        services: ["service1", "service2"],
        consts: {
          THRESHOLD: "100",
          API_ENDPOINT: "https://api.example.com",
        },
        steps: [
          {
            id: "step-1",
            name: "Step 1",
            provider: {
              type: "mock",
              config: "mock-config",
              with: {
                enrich_alert: [{ key: "alert_key", value: "alert_value" }],
              },
            },
            if: "'{{ alert.severity }}' == 'critical'",
            vars: {
              STEP_THRESHOLD: "{{ consts.THRESHOLD }}",
            },
          },
        ],
        actions: [
          {
            id: "action-1",
            name: "Action 1",
            provider: {
              type: "mock",
              config: "mock-config",
              with: {
                enrich_incident: [
                  { key: "incident_key", value: "incident_value" },
                ],
              },
            },
          },
        ],
        triggers: [
          {
            type: "manual",
          },
          {
            type: "alert",
            filters: [
              { key: "severity", value: "critical" },
              { key: "service", value: "api" },
            ],
          },
        ],
      },
    };

    expect(() =>
      YamlWorkflowDefinitionSchema.parse(fullWorkflow)
    ).not.toThrow();
  });

  it("should fail validation when required fields are missing", () => {
    const invalidWorkflow = {
      workflow: {
        name: "Invalid Workflow",
        steps: [
          {
            name: "test-step",
            provider: {
              type: "mock",
              config: "mock-config",
              with: {},
            },
          },
        ],
        triggers: [
          {
            type: "manual",
          },
        ],
      },
    };

    expect(() => YamlWorkflowDefinitionSchema.parse(invalidWorkflow)).toThrow();
  });

  it("should fail validation when steps are empty", () => {
    const invalidWorkflow = {
      workflow: {
        id: "test-workflow-id",
        steps: [],
        triggers: [
          {
            type: "manual",
          },
        ],
      },
    };

    expect(() => YamlWorkflowDefinitionSchema.parse(invalidWorkflow)).toThrow();
  });

  it("should validate a workflow with enrich_alert in provider config", () => {
    const workflowWithEnrichAlert = {
      workflow: {
        id: "test-workflow-id",
        steps: [
          {
            name: "step-with-enrich-alert",
            provider: {
              type: "mock",
              config: "mock-config",
              with: {
                enrich_alert: [
                  { key: "alert_key1", value: "alert_value1" },
                  { key: "alert_key2", value: "alert_value2" },
                ],
              },
            },
          },
        ],
        triggers: [
          {
            type: "manual",
          },
        ],
      },
    };

    expect(() =>
      YamlWorkflowDefinitionSchema.parse(workflowWithEnrichAlert)
    ).not.toThrow();
  });

  it("should validate a workflow with enrich_incident in provider config", () => {
    const workflowWithEnrichIncident = {
      workflow: {
        id: "test-workflow-id",
        steps: [
          {
            name: "step-with-enrich-incident",
            provider: {
              type: "mock",
              config: "mock-config",
              with: {
                enrich_incident: [
                  { key: "incident_key1", value: "incident_value1" },
                  { key: "incident_key2", value: "incident_value2" },
                ],
              },
            },
          },
        ],
        triggers: [
          {
            type: "manual",
          },
        ],
      },
    };

    expect(() =>
      YamlWorkflowDefinitionSchema.parse(workflowWithEnrichIncident)
    ).not.toThrow();
  });

  it("should validate a workflow with both enrich_alert and enrich_incident in provider config", () => {
    const workflowWithBothEnrichments = {
      workflow: {
        id: "test-workflow-id",
        steps: [
          {
            name: "step-with-both-enrichments",
            provider: {
              type: "mock",
              config: "mock-config",
              with: {
                enrich_alert: [{ key: "alert_key", value: "alert_value" }],
                enrich_incident: [
                  { key: "incident_key", value: "incident_value" },
                ],
                param1: "value1",
              },
            },
          },
        ],
        triggers: [
          {
            type: "manual",
          },
        ],
      },
    };

    expect(() =>
      YamlWorkflowDefinitionSchema.parse(workflowWithBothEnrichments)
    ).not.toThrow();
  });

  it("should validate a workflow with disposable property in enrich_alert", () => {
    const workflowWithDisposableEnrichAlert = {
      workflow: {
        id: "test-workflow-id",
        steps: [
          {
            name: "step-with-disposable-enrich-alert",
            provider: {
              type: "mock",
              config: "mock-config",
              with: {
                enrich_alert: [
                  {
                    key: "disposable_alert_key",
                    value: "disposable_alert_value",
                    disposable: true,
                  },
                  {
                    key: "non_disposable_alert_key",
                    value: "non_disposable_alert_value",
                    disposable: false,
                  },
                  {
                    key: "unspecified_disposable_alert_key",
                    value: "unspecified_disposable_alert_value",
                  },
                ],
              },
            },
          },
        ],
        triggers: [
          {
            type: "manual",
          },
        ],
      },
    };

    expect(() =>
      YamlWorkflowDefinitionSchema.parse(workflowWithDisposableEnrichAlert)
    ).not.toThrow();
  });

  it("should validate enrichment fields with the correct schema types", () => {
    const schema = getYamlWorkflowDefinitionSchema([]);
    const workflowWithMixedEnrichments = {
      workflow: {
        id: "test-workflow-id",
        name: "Test Workflow",
        description: "Test workflow with mixed enrichments",
        steps: [
          {
            name: "Step With Mixed Enrichments",
            provider: {
              type: "mock",
              with: {
                enrich_alert: [
                  {
                    key: "disposable_key",
                    value: "value",
                    disposable: true,
                  },
                ],
                enrich_incident: [
                  {
                    key: "incident_key",
                    value: "incident_value",
                    // Incident enrichment should not have disposable property
                  },
                ],
              },
            },
          },
        ],
        triggers: [{ type: "manual" }],
      },
    };

    expect(() => schema.parse(workflowWithMixedEnrichments)).not.toThrow();
  });
});

describe("getYamlWorkflowDefinitionSchema", () => {
  const mockProviders: Provider[] = [
    {
      id: "provider1",
      display_name: "Provider 1",
      tags: [],
      type: "provider1",
      can_query: true,
      can_notify: true,
      query_params: ["param1", "param2"],
      notify_params: ["param3", "param4"],
      config: {},
      installed: true,
      linked: true,
      last_alert_received: "",
      details: {
        authentication: {},
      },
      pulling_available: false,
      validatedScopes: {},
      pulling_enabled: false,
      categories: [],
      coming_soon: false,
      health: false,
    },
  ];

  it("should generate schema with providers", () => {
    const schema = getYamlWorkflowDefinitionSchema(mockProviders);
    const validWorkflow = {
      workflow: {
        id: "test-workflow-id",
        name: "Test Workflow",
        description: "Test description",
        steps: [
          {
            name: "Test Step",
            provider: {
              type: "provider1",
              with: {
                param1: "value1",
                param2: "value2",
              },
            },
          },
        ],
        triggers: [
          {
            type: "manual",
          },
        ],
      },
    };

    expect(() => schema.parse(validWorkflow)).not.toThrow();
  });

  it("should generate partial schema when partial option is true", () => {
    const schema = getYamlWorkflowDefinitionSchema(mockProviders, {
      partial: true,
    });
    const partialWorkflow = {
      workflow: {
        id: "test-workflow-id",
        triggers: [
          {
            type: "manual",
          },
        ],
      },
    };

    expect(() => schema.parse(partialWorkflow)).not.toThrow();
  });

  it("should validate different trigger types", () => {
    const schema = getYamlWorkflowDefinitionSchema(mockProviders);
    const workflowWithAllTriggers = {
      workflow: {
        id: "test-workflow-id",
        name: "Test Workflow",
        description: "Test description",
        steps: [
          {
            name: "Test Step",
            provider: {
              type: "provider1",
              with: {
                param1: "value1",
              },
            },
          },
        ],
        triggers: [
          {
            type: "manual",
          },
          {
            type: "alert",
            filters: [{ key: "severity", value: "critical" }],
          },
          {
            type: "interval",
            value: "10m",
          },
          {
            type: "incident",
            events: ["created"],
          },
        ],
      },
    };

    expect(() => schema.parse(workflowWithAllTriggers)).not.toThrow();
  });

  it("should validate enrichment fields in generated schema", () => {
    const schema = getYamlWorkflowDefinitionSchema(mockProviders);
    const workflowWithEnrichments = {
      workflow: {
        id: "test-workflow-id",
        name: "Test Workflow",
        description: "Test description",
        steps: [
          {
            name: "Test Step",
            provider: {
              type: "provider1",
              with: {
                param1: "value1",
                enrich_alert: [
                  { key: "alert_enrichment", value: "alert_value" },
                ],
                enrich_incident: [
                  { key: "incident_enrichment", value: "incident_value" },
                ],
              },
            },
          },
        ],
        triggers: [
          {
            type: "manual",
          },
        ],
      },
    };

    expect(() => schema.parse(workflowWithEnrichments)).not.toThrow();
  });

  it("should validate disposable property in enrich_alert in generated schema", () => {
    const schema = getYamlWorkflowDefinitionSchema(mockProviders);
    const workflowWithDisposableEnrichAlert = {
      workflow: {
        id: "test-workflow-id",
        name: "Test Workflow",
        description: "Test description",
        steps: [
          {
            name: "Test Step",
            provider: {
              type: "provider1",
              with: {
                param1: "value1",
                enrich_alert: [
                  {
                    key: "alert_enrichment",
                    value: "alert_value",
                    disposable: true,
                  },
                  {
                    key: "another_alert_enrichment",
                    value: "another_alert_value",
                    disposable: false,
                  },
                ],
                enrich_incident: [
                  {
                    key: "incident_enrichment",
                    value: "incident_value",
                    // No disposable property here
                  },
                ],
              },
            },
          },
        ],
        triggers: [
          {
            type: "manual",
          },
        ],
      },
    };

    expect(() => schema.parse(workflowWithDisposableEnrichAlert)).not.toThrow();
  });
});
