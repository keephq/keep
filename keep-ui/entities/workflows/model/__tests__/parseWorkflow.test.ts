import { Provider } from "@/shared/api/providers";
import {
  getOrderedWorkflowYamlStringFromJSON,
  parseWorkflowYamlStringToJSON,
} from "../../lib/reorderWorkflowSections";

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
`;

const providers: Provider[] = [
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
    display_name: "Clickhouse",
    can_query: true,
    can_notify: true,
    validatedScopes: {},
    tags: [],
    pulling_available: true,
    pulling_enabled: true,
    categories: [],
    coming_soon: false,
    health: true,
  },
  {
    id: "gcp",
    type: "gcpmonitoring",
    config: {},
    installed: true,
    linked: true,
    last_alert_received: "",
    details: {
      authentication: {},
    },
    display_name: "GCP",
    can_query: true,
    can_notify: true,
    validatedScopes: {},
    tags: [],
    pulling_available: true,
    pulling_enabled: true,
    categories: [],
    coming_soon: false,
    health: true,
  },
  {
    id: "openai",
    type: "openai",
    config: {},
    installed: true,
    linked: true,
    details: {
      authentication: {},
    },
    last_alert_received: "",
    display_name: "OpenAI",
    can_query: true,
    can_notify: true,
    validatedScopes: {},
    tags: [],
    pulling_available: true,
    pulling_enabled: true,
    categories: [],
    coming_soon: false,
    health: true,
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
    display_name: "Slack",
    can_query: true,
    can_notify: true,
    validatedScopes: {},
    tags: [],
    pulling_available: true,
    pulling_enabled: true,
    categories: [],
    coming_soon: false,
    health: true,
  },
];

describe("YAML Parser", () => {
  // it("should parse workflow into a definition and serialize it back to YAML Definition", () => {
  //   const parsedWorkflowDefinition = parseWorkflow(
  //     clickhouseExampleYaml,
  //     providers
  //   );
  //   const yamlDefinitionWorkflow = {
  //     workflow: getWorkflowFromDefinition(parsedWorkflowDefinition),
  //   };
  //   expect(yamlDefinitionWorkflow).toEqual(expectedWorkflow);
  // });

  it("should parse yaml string and serialize it back to yaml string", () => {
    // const reorderedWorkflow = orderWorkflowYamlString(
    //   unorderedClickhouseExampleYaml
    // );
    const workflowJSON = parseWorkflowYamlStringToJSON(
      unorderedClickhouseExampleYaml
    );
    const reorderedWorkflow =
      getOrderedWorkflowYamlStringFromJSON(workflowJSON);
    expect(reorderedWorkflow.trim()).toEqual(clickhouseExampleYaml.trim());
  });
});
