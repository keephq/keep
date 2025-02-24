import { Provider } from "@/shared/api/providers";
import {
  getWorkflowFromDefinition,
  loadWorkflowYAML,
  parseWorkflow,
} from "../../lib/parser";
import { dump } from "js-yaml";
import { loadWorkflowIntoOrderedYaml } from "../../lib/reorderWorkflowSections";

const exampleYaml = `
workflow:
  id: enrich-gcp-alert
  name: 5a76aa52-4e0f-43c3-85ff-5603229c5d7e
  description: Enriched GCP Alert
  disabled: false
  triggers:
    - type: manual
    - filters:
        - key: source
          value: gcpmonitoring
      type: alert
  consts: {}
  owners: []
  services: []
  steps:
    - name: gcpmonitoring-step
      provider:
        config: "{{ providers.gcp }}"
        type: gcpmonitoring
        with:
          as_json: false
          filter: resource.type = "cloud_run_revision" {{alert.traceId}}
          page_size: 1000
          raw: false
          timedelta_in_days: 1
    - name: openai-step
      provider:
        config: "{{ providers.openai }}"
        type: openai
        with:
          prompt:
            "You are a very talented engineer that receives context from GCP logs
            about an endpoint that returned 500 status code and reports back the root
            cause analysis. Here is the context: keep.json_dumps({{steps.gcpmonitoring-step.results}}) (it is a JSON list of log entries from GCP Logging).
            In your answer, also provide the log entry that made you conclude the root cause and specify what your certainty level is that it is the root cause. (between 1-10, where 1 is low and 10 is high)"
  actions:
    - name: slack-action
      provider:
        config: "{{ providers.slack }}"
        type: slack
        with:
          message: "{{steps.openai-step.results}}"
`;

const providers: Provider[] = [
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
const expectedWorkflow = loadWorkflowYAML(exampleYaml);

describe("YAML Parser", () => {
  it("should parse workflow into a definition and serialize it back to YAML Definition", () => {
    const parsedWorkflowDefinition = parseWorkflow(exampleYaml, providers);
    const yamlDefinitionWorkflow = {
      workflow: getWorkflowFromDefinition(parsedWorkflowDefinition),
    };
    expect(yamlDefinitionWorkflow).toEqual(expectedWorkflow);
  });

  it("should parse yaml string and serialize it back to yaml string", () => {
    const parsedWorkflowDefinition = parseWorkflow(exampleYaml, providers);
    const orderedWorkflow = {
      workflow: getWorkflowFromDefinition(parsedWorkflowDefinition),
    };
    const serializedWorkflow = dump(orderedWorkflow, {
      indent: 2,
      lineWidth: -1,
      noRefs: true,
      sortKeys: false,
      quotingType: '"',
    });
    const reorderedWorkflow = loadWorkflowIntoOrderedYaml(serializedWorkflow);
    expect(reorderedWorkflow).toEqual(exampleYaml);
  });
});
