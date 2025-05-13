import { Provider } from "@/shared/api/providers";
import { getYamlWorkflowDefinitionSchema } from "../../model/yaml.schema";
import {
  getOrderedWorkflowYamlString,
  parseWorkflowYamlToJSON,
} from "../yaml-utils";

const unorderedClickhouseExampleYaml = `
workflow:
  id: query-clickhouse
  consts: {}
  owners: []
  services: []
  steps:
    - name: clickhouse-step
      provider:
        config: "{{ providers.clickhouse }}"
        type: clickhouse
        with:
          query: "SELECT * FROM logs_table ORDER BY timestamp DESC LIMIT 1;"
          single_row: "True"

  actions:
    - name: ntfy-action
      if: "'{{ steps.clickhouse-step.results.level }}' == 'ERROR'"
      provider:
        config: "{{ providers.ntfy }}"
        type: ntfy
        with:
          message: "Error in clickhouse logs_table: {{ steps.clickhouse-step.results.level }}"
          topic: clickhouse

    - name: slack-action
      if: "'{{ steps.clickhouse-step.results.level }}' == 'ERROR'"
      provider:
        config: "{{ providers.slack }}"
        type: slack
        with:
          message: "Error in clickhouse logs_table: {{ steps.clickhouse-step.results.level }}"
  name: Query Clickhouse and send an alert if there is an error
  description: Query Clickhouse and send an alert if there is an error
  disabled: false
  triggers:
    - type: manual
`;

const clickhouseExampleYaml = `
workflow:
  id: query-clickhouse
  name: Query Clickhouse and send an alert if there is an error
  description: Query Clickhouse and send an alert if there is an error
  disabled: false
  triggers:
    - type: manual
  consts: {}
  owners: []
  services: []
  steps:
    - name: clickhouse-step
      provider:
        type: clickhouse
        config: "{{ providers.clickhouse }}"
        with:
          query: "SELECT * FROM logs_table ORDER BY timestamp DESC LIMIT 1;"
          single_row: "True"

  actions:
    - name: ntfy-action
      if: "'{{ steps.clickhouse-step.results.level }}' == 'ERROR'"
      provider:
        type: ntfy
        config: "{{ providers.ntfy }}"
        with:
          message: "Error in clickhouse logs_table: {{ steps.clickhouse-step.results.level }}"
          topic: clickhouse

    - name: slack-action
      if: "'{{ steps.clickhouse-step.results.level }}' == 'ERROR'"
      provider:
        type: slack
        config: "{{ providers.slack }}"
        with:
          message: "Error in clickhouse logs_table: {{ steps.clickhouse-step.results.level }}"
`;

const multilineClickhouseExampleYaml = `
workflow:
  id: query-clickhouse
  name: Query Clickhouse and send an alert if there is an error
  description: Query Clickhouse and send an alert if there is an error
  disabled: false
  triggers:
    - type: manual
  steps:
    - name: clickhouse-observability-urls
      provider:
        type: clickhouse
        config: "{{ providers.clickhouse }}"
        with:
          query: |
            SELECT Url, Status FROM "observability"."Urls"
            WHERE ( Url LIKE '%te_tests%' ) AND Timestamp >= toStartOfMinute(date_add(toDateTime(NOW()), INTERVAL -1 MINUTE)) AND Status = 0;
        on-failure:
          retry:
            count: 1
`;

describe("YAML Utils", () => {
  it("getOrderedWorkflowYamlString should reorder the workflow sections while keeping the quote style", () => {
    const reorderedWorkflow = getOrderedWorkflowYamlString(
      unorderedClickhouseExampleYaml
    );
    expect(reorderedWorkflow.trim()).toEqual(clickhouseExampleYaml.trim());
  });

  it("getOrderedWorkflowYamlStringFromJSON should return the same string if the input is already ordered", () => {
    const orderedWorkflow = getOrderedWorkflowYamlString(clickhouseExampleYaml);
    expect(orderedWorkflow.trim()).toEqual(clickhouseExampleYaml.trim());
  });

  it("getOrderedWorkflowYamlString should return the same string if the input", () => {
    const orderedWorkflow = getOrderedWorkflowYamlString(
      multilineClickhouseExampleYaml
    );
    expect(orderedWorkflow.trim()).toEqual(
      multilineClickhouseExampleYaml.trim()
    );
  });

  it("parseWorkflowYamlToJSON should return json with workflow section if the input is not wrapped in workflow section", () => {
    const parsed = parseWorkflowYamlToJSON(clickhouseExampleYaml);
    expect(parsed.success).toBe(true);
    expect(parsed.data).toHaveProperty("workflow");
  });

  it("parseWorkflowYamlToJSON should parse the workflow with mock providers", () => {
    const mockProviders: Provider[] = [
      {
        id: "clickhouse",
        type: "clickhouse",
        config: {},
        installed: true,
        linked: true,
        last_alert_received: "",
        details: {
          authentication: {},
        },
        display_name: "Mock Clickhouse Provider",
        can_query: true,
        query_params: ["query", "single_row"],
        can_notify: false,
        validatedScopes: {},
        tags: [],
        pulling_available: true,
        pulling_enabled: true,
        categories: [],
        coming_soon: false,
        health: false,
      },
      {
        id: "ntfy",
        type: "ntfy",
        config: {},
        installed: true,
        linked: true,
        can_query: false,
        can_notify: true,
        notify_params: ["message", "topic"],
        details: {
          authentication: {},
        },
        display_name: "Mock Ntfy Provider",
        validatedScopes: {},
        tags: [],
        pulling_available: true,
        pulling_enabled: true,
        last_alert_received: "",
        categories: [],
        coming_soon: false,
        health: false,
      },
      {
        id: "slack",
        type: "slack",
        config: {},
        installed: true,
        linked: true,
        last_alert_received: "",
        details: {
          authentication: {},
        },
        display_name: "Mock Slack Provider",
        can_query: false,
        can_notify: true,
        notify_params: ["message"],
        validatedScopes: {},
        tags: [],
        pulling_available: true,
        pulling_enabled: true,
        categories: [],
        coming_soon: false,
        health: false,
      },
    ];
    const zodSchema = getYamlWorkflowDefinitionSchema(mockProviders);
    const parsed = parseWorkflowYamlToJSON(clickhouseExampleYaml, zodSchema);
    expect(parsed.success).toBe(true);
    expect(parsed.data).toHaveProperty("workflow");
  });
});
