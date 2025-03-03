import { getOrderedWorkflowYamlString } from "../yaml-utils";

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
});
