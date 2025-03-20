import {
  V2ActionSchema,
  V2StepConditionThresholdSchema,
  V2StepForeachSchema,
  V2StepStepSchema,
  V2StepConditionAssertSchema,
} from "../types";
import {
  conditionThresholdTemplate,
  foreachTemplate,
} from "@/features/workflows/builder/lib/utils";

describe("V2ActionSchema", () => {
  it("should validate a Jira ticket creation action with enrichment and custom properties", () => {
    const jiraAction = {
      id: "d46d3c81-d765-4417-ba93-63a3a027e766",
      name: "create-jira-ticket-oncall-board",
      componentType: "task",
      type: "action-jira",
      properties: {
        config: "  jira  ",
        with: {
          board_name: "Oncall Board",
          custom_fields: {
            customfield_10201: "Critical",
          },
          description:
            '"This ticket was created by Keep.\nPlease check the alert details below:\n{code:json} {{ alert }} {code}"\n',
          enrich_alert: [
            {
              key: "ticket_type",
              value: "jira",
            },
            {
              key: "ticket_id",
              value: "results.issue.key",
            },
            {
              key: "ticket_url",
              value: "results.ticket_url",
            },
          ],
          issuetype: "Task",
          summary:
            "{{ alert.name }} - {{ alert.description }} (created by Keep)",
        },
        stepParams: ["ticket_id", "board_id", "kwargs"],
        actionParams: [
          "summary",
          "description",
          "issue_type",
          "project_key",
          "board_name",
          "issue_id",
          "labels",
          "components",
          "custom_fields",
          "kwargs",
        ],
        if: "'{{ alert.service }}' == 'ftp' and not '{{ alert.ticket_id }}'",
      },
    };

    expect(() => V2ActionSchema.parse(jiraAction)).not.toThrow();
  });

  it("should validate an action with both enrichment types", () => {
    const actionWithBothEnrichments = {
      id: "test-id",
      name: "test-action",
      componentType: "task",
      type: "action-test",
      properties: {
        actionParams: ["param1"],
        with: {
          enrich_alert: [{ key: "test", value: "value" }],
          enrich_incident: [{ key: "test", value: "value" }],
          customParam: "value",
          numericParam: 123,
          objectParam: { test: "value" },
        },
      },
    };

    expect(() => V2ActionSchema.parse(actionWithBothEnrichments)).not.toThrow();
  });
});

describe("V2StepConditionThresholdSchema", () => {
  it("should validate a condition threshold template with an id", () => {
    const template = {
      ...conditionThresholdTemplate,
      id: "test-id",
    };

    expect(() => V2StepConditionThresholdSchema.parse(template)).not.toThrow();
  });

  it("should fail validation when id is missing", () => {
    expect(() =>
      V2StepConditionThresholdSchema.parse(conditionThresholdTemplate)
    ).toThrow();
  });

  it("should validate a complete condition threshold with branches", () => {
    const completeThreshold = {
      ...conditionThresholdTemplate,
      id: "test-id",
      properties: {
        value: "100",
        compare_to: "200",
      },
      branches: {
        true: [],
        false: [],
      },
    };

    expect(() =>
      V2StepConditionThresholdSchema.parse(completeThreshold)
    ).not.toThrow();
  });
});

describe("V2StepForeachSchema", () => {
  it("should validate a foreach step with an id", () => {
    const foreachStep = {
      ...foreachTemplate,
      id: "test-id",
    };

    expect(() => V2StepForeachSchema.parse(foreachStep)).not.toThrow();
  });
});

describe("V2StepStepSchema", () => {
  it("should validate a basic step with required fields", () => {
    const basicStep = {
      id: "test-step-id",
      name: "test-step",
      componentType: "task",
      type: "step-test",
      properties: {
        stepParams: ["param1", "param2"],
      },
    };

    expect(() => V2StepStepSchema.parse(basicStep)).not.toThrow();
  });

  it("should validate a step with all optional fields", () => {
    const fullStep = {
      id: "test-step-id",
      name: "test-step",
      componentType: "task",
      type: "step-test",
      properties: {
        stepParams: ["param1", "param2"],
        config: "test-config",
        vars: {
          key1: "value1",
          key2: "value2",
        },
        if: "'{{ alert.service }}' == 'test'",
        with: {
          enrich_alert: [{ key: "test_key", value: "test_value" }],
          enrich_incident: [{ key: "incident_key", value: "incident_value" }],
          customField: "custom_value",
          numericField: 123,
          objectField: { test: "value" },
        },
      },
    };

    expect(() => V2StepStepSchema.parse(fullStep)).not.toThrow();
  });

  it("should fail validation when id is missing", () => {
    const invalidStep = {
      name: "test-step",
      componentType: "task",
      type: "step-test",
      properties: {
        stepParams: ["param1"],
      },
    };

    expect(() => V2StepStepSchema.parse(invalidStep)).toThrow();
  });

  it("should fail validation when type doesn't start with 'step'", () => {
    const invalidStep = {
      id: "test-id",
      name: "test-step",
      componentType: "task",
      type: "invalid-type",
      properties: {
        stepParams: ["param1"],
      },
    };

    expect(() => V2StepStepSchema.parse(invalidStep)).toThrow();
  });

  it("should validate a step with body", () => {
    const bodyStep = {
      id: "test-step-id",
      name: "test-step",
      componentType: "task",
      type: "step-test",
      properties: {
        stepParams: ["param1", "param2"],
        config: "test-config",
        vars: {
          key1: "value1",
          key2: "value2",
        },
        if: "'{{ alert.service }}' == 'test'",
        with: {
          enrich_alert: [{ key: "test_key", value: "test_value" }],
          enrich_incident: [{ key: "incident_key", value: "incident_value" }],
          body: {
            key: "value",
          }
        },
      },
    };

    expect(V2StepStepSchema.parse(bodyStep).properties.with?.body).toEqual({key: "value"});
  });

});

describe("V2StepConditionAssertSchema", () => {
  it("should validate a basic condition assert with empty branches", () => {
    const basicAssert = {
      id: "test-assert-id",
      name: "test-assert",
      componentType: "switch",
      type: "condition-assert",
      properties: {
        assert: "'{{ alert.severity }}' == 'critical'",
      },
      branches: {
        true: [],
        false: [],
      },
    };

    expect(() => V2StepConditionAssertSchema.parse(basicAssert)).not.toThrow();
  });

  it("should validate a condition assert with populated branches", () => {
    const assertWithBranches = {
      id: "test-assert-id",
      name: "test-assert",
      componentType: "switch",
      type: "condition-assert",
      properties: {
        assert: "'{{ alert.severity }}' == 'critical'",
      },
      branches: {
        true: [
          {
            id: "action-1",
            name: "test-action",
            componentType: "task",
            type: "action-test",
            properties: {
              actionParams: ["param1"],
            },
          },
        ],
        false: [
          {
            id: "step-1",
            name: "test-step",
            componentType: "task",
            type: "step-test",
            properties: {
              stepParams: ["param1"],
            },
          },
        ],
      },
    };

    expect(() =>
      V2StepConditionAssertSchema.parse(assertWithBranches)
    ).not.toThrow();
  });

  it("should fail validation when assert property is missing", () => {
    const invalidAssert = {
      id: "test-assert-id",
      name: "test-assert",
      componentType: "switch",
      type: "condition-assert",
      properties: {},
      branches: {
        true: [],
        false: [],
      },
    };

    expect(() => V2StepConditionAssertSchema.parse(invalidAssert)).toThrow();
  });

  it("should fail validation when branches are missing", () => {
    const invalidAssert = {
      id: "test-assert-id",
      name: "test-assert",
      componentType: "switch",
      type: "condition-assert",
      properties: {
        assert: "'{{ alert.severity }}' == 'critical'",
      },
    };

    expect(() => V2StepConditionAssertSchema.parse(invalidAssert)).toThrow();
  });
});
