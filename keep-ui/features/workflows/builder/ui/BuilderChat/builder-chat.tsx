import { useCallback, useMemo, useState } from "react";
import { Provider } from "@/app/(keep)/providers/providers";
import {
  V2Step,
  FlowNode,
  ToolboxConfiguration,
  V2StepStep,
  DefinitionV2,
  IncidentEventEnum,
  V2ActionStep,
  V2ActionSchema,
  V2StepStepSchema,
  V2StepConditionAssert,
  V2StepConditionThreshold,
  V2StepConditionAssertSchema,
  V2StepCondition,
  V2StepConditionSchema,
} from "@/entities/workflows/model/types";
import {
  CopilotChat,
  CopilotKitCSSProperties,
  useCopilotChatSuggestions,
} from "@copilotkit/react-ui";
import { useWorkflowStore } from "@/entities/workflows";
import {
  useCopilotAction,
  useCopilotChat,
  useCopilotReadable,
} from "@copilotkit/react-core";
import { Button, Link } from "@/components/ui";
import { generateStepDefinition } from "@/app/(keep)/workflows/builder/_actions/getStepJson";
import { GENERAL_INSTRUCTIONS } from "@/app/(keep)/workflows/builder/_constants";
import { showSuccessToast } from "@/shared/ui/utils/showSuccessToast";
import { WF_DEBUG_INFO } from "../debug-settings";
import { AddTriggerUI } from "./AddTriggerUI";
import { useTestStep } from "../Editor/StepTest";
import { useConfig } from "@/utils/hooks/useConfig";
import { Title, Text } from "@tremor/react";
import { SparklesIcon } from "@heroicons/react/24/outline";
import BuilderChatPlaceholder from "./ai-workflow-placeholder.png";
import Image from "next/image";
import { Edge } from "@xyflow/react";
import { SuggestionResult } from "./SuggestionStatus";
import { useSearchAlerts } from "@/utils/hooks/useSearchAlerts";
import "@copilotkit/react-ui/styles.css";
import "./chat.css";
import Skeleton from "react-loading-skeleton";
import { AddStepUI } from "./AddStepUI";

const useAlertKeys = () => {
  const defaultQuery = {
    combinator: "or",
    rules: [
      {
        combinator: "and",
        rules: [{ field: "source", operator: "=", value: "" }],
      },
      {
        combinator: "and",
        rules: [{ field: "source", operator: "=", value: "" }],
      },
    ],
  };
  const { data: alertsFound = [], isLoading } = useSearchAlerts({
    query: defaultQuery,
    timeframe: 3600 * 24,
  });

  const keys = useMemo(() => {
    const getNestedKeys = (obj: any, prefix = ""): string[] => {
      return Object.entries(obj).reduce<string[]>((acc, [key, value]) => {
        const newKey = prefix ? `${prefix}.${key}` : key;
        if (value && typeof value === "object" && !Array.isArray(value)) {
          return [...acc, ...getNestedKeys(value, newKey)];
        }
        return [...acc, newKey];
      }, []);
    };
    return [
      ...alertsFound.reduce<Set<string>>((acc, alert) => {
        const alertKeys = getNestedKeys(alert);
        return new Set([...acc, ...alertKeys]);
      }, new Set<string>()),
    ];
  }, [alertsFound]);

  return { keys, isLoading };
};

interface BuilderChatProps {
  definition: DefinitionV2;
  installedProviders: Provider[];
}

function getWorkflowSummaryForCopilot(nodes: FlowNode[], edges: Edge[]) {
  return {
    nodes: nodes.map((n) => ({
      id: n.id,
      nextStepId: n.nextStepId,
      prevStepId: n.prevStepId,
      ...n.data,
    })),
    edges: edges.map((e) => ({ id: e.id, source: e.source, target: e.target })),
  };
}

function isProtectedStep(stepId: string) {
  return (
    stepId === "start" ||
    stepId === "end" ||
    stepId === "trigger_start" ||
    stepId === "trigger_end"
  );
}

const AddTriggerSkeleton = () => {
  return (
    <div className="flex flex-col gap-2">
      <div className="h-4 w-full">
        <Skeleton />
      </div>
      <div className="h-4 w-1/2">
        <Skeleton />
      </div>
      <div className="h-12 max-w-[250px] w-full rounded-md">
        <Skeleton className="w-full h-full" />
      </div>
    </div>
  );
};

export function BuilderChat({
  definition,
  installedProviders,
}: BuilderChatProps) {
  const {
    nodes,
    edges,
    toolboxConfiguration,
    addNodeBetween,
    selectedEdge,
    selectedNode,
    deleteNodes,
    validationErrors,
  } = useWorkflowStore();

  const steps = useMemo(() => {
    if (!toolboxConfiguration || !toolboxConfiguration.groups) {
      return [];
    }
    const result = [];
    for (const group of toolboxConfiguration.groups) {
      if (group.name !== "Triggers") {
        // Type guard to filter out triggers
        const nonTriggerSteps = group.steps.filter(
          (step): step is Omit<V2Step, "id"> => step.componentType !== "trigger"
        );
        result.push(...nonTriggerSteps);
      }
    }
    return result;
  }, [toolboxConfiguration]);

  const workflowSummary = useMemo(() => {
    return getWorkflowSummaryForCopilot(nodes, edges);
  }, [nodes, edges]);

  useCopilotReadable(
    {
      description: "Current workflow",
      value: workflowSummary,
    },
    [workflowSummary]
  );

  useCopilotReadable(
    {
      description: "Installed providers",
      value: installedProviders,
      convert: (description, installedProviders: Provider[]) => {
        return installedProviders
          .map((p) => `${p.type}, id: ${p.id}`)
          .join(", ");
      },
    },
    [installedProviders]
  );

  useCopilotReadable(
    {
      description: "These are steps that you can add to the workflow",
      value: toolboxConfiguration,
      convert: (description, toolboxConfiguration: ToolboxConfiguration) => {
        const result: string[] = [];
        toolboxConfiguration?.groups?.forEach((group) => {
          result.push(
            `==== ${group.name}, componentType: ${group.steps[0].componentType} ====`
          );
          group.steps.forEach((step) => {
            result.push(
              `${step.type}, properties: ${JSON.stringify(step.properties)}`
            );
          });
        });
        return result.join("\n");
      },
    },
    [steps]
  );

  useCopilotReadable(
    {
      description: "Selected node id",
      value: selectedNode,
    },
    [selectedNode]
  );

  useCopilotReadable(
    {
      description: "Validation errors",
      value: validationErrors,
    },
    [validationErrors]
  );

  useCopilotChatSuggestions(
    {
      instructions:
        "Suggest the most relevant next actions. E.g. if workflow is empty ask what workflow user is trying to build, if workflow already has some steps, suggest either to explain or add a new step. If some step is selected, suggest to explain it or help to configure it. If there are validation errors, suggest to fix them. If you waiting for user to accept or reject the suggestion, suggest relevant short answers.",
      minSuggestions: 1,
      maxSuggestions: 3,
    },
    [nodes, steps, selectedNode]
  );

  const { setMessages } = useCopilotChat();

  const { v2Properties: properties, updateV2Properties: setProperties } =
    useWorkflowStore();

  useCopilotAction({
    name: "changeWorkflowName",
    description: "Change the name of the workflow",
    parameters: [
      {
        name: "name",
        description: "The new name of the workflow",
        type: "string",
        required: true,
      },
    ],
    handler: ({ name }: { name: string }) => {
      setProperties({ ...properties, name });
      showSuccessToast("Workflow name updated");
    },
  });

  useCopilotAction({
    name: "changeWorkflowDescription",
    description: "Change the description of the workflow",
    parameters: [
      {
        name: "description",
        description: "The new description of the workflow",
        type: "string",
        required: true,
      },
    ],
    handler: ({ description }: { description: string }) => {
      setProperties({ ...properties, description });
      showSuccessToast("Workflow description updated");
    },
  });

  useCopilotAction({
    name: "removeStepNode",
    description: "Remove a step from the workflow",
    parameters: [
      {
        name: "stepType",
        description: "The type of step to remove",
        type: "string",
        required: true,
      },
      {
        name: "stepId",
        description: "The id of the step to remove",
        type: "string",
        required: true,
      },
    ],
    renderAndWaitForResponse: ({ status, args, respond }) => {
      if (status === "inProgress") {
        return <div>Loading...</div>;
      }
      const stepId = args.stepId;
      if (isProtectedStep(stepId)) {
        respond?.(
          "Cannot remove start, end, trigger_start or trigger_end steps"
        );
        return (
          <p>Cannot remove start, end, trigger_start or trigger_end steps</p>
        );
      }
      // TODO: nice UI for this
      if (confirm(`Are you sure you want to remove ${stepId} step?`)) {
        const deletedNodeIds = deleteNodes(stepId);
        if (deletedNodeIds.length > 0) {
          respond?.("Step removed");
          return <p>Step {stepId} removed</p>;
        } else {
          respond?.("Step removal failed");
          return <p>Step removal failed</p>;
        }
      } else {
        respond?.("User cancelled the step removal");
        return <p>Step removal cancelled</p>;
      }
    },
  });

  useCopilotAction({
    name: "removeTriggerNode",
    description: "Remove a trigger from the workflow",
    parameters: [
      {
        name: "triggerNodeId",
        description:
          "The id of the trigger to remove. One of 'manual', 'alert', 'incident', 'interval'",
        type: "string",
        required: true,
      },
    ],
    renderAndWaitForResponse: ({ status, args, respond }) => {
      if (status === "inProgress") {
        return <div>Loading...</div>;
      }
      const triggerNodeId = args.triggerNodeId;

      if (isProtectedStep(triggerNodeId)) {
        respond?.(
          "Cannot remove start, end, trigger_start or trigger_end steps"
        );
        return (
          <p>Cannot remove start, end, trigger_start or trigger_end steps</p>
        );
      }

      // TODO: nice UI for this
      if (
        confirm(`Are you sure you want to remove ${triggerNodeId} trigger?`)
      ) {
        const deletedNodeIds = deleteNodes(triggerNodeId);
        if (deletedNodeIds.length > 0) {
          respond?.("Trigger removed");
          return <p>Trigger {triggerNodeId} removed</p>;
        } else {
          respond?.("Trigger removal failed");
          return <p>Trigger removal failed</p>;
        }
      } else {
        respond?.("User cancelled the trigger removal");
        return <p>Trigger removal cancelled</p>;
      }
    },
  });

  useCopilotAction({
    name: "addManualTrigger",
    description:
      "Add a manual trigger to the workflow. There could be only one manual trigger in the workflow.",
    parameters: [],
    renderAndWaitForResponse: (args) => {
      if (args.status === "inProgress") {
        return <AddTriggerSkeleton />;
      }

      if (args.status === "complete" && "result" in args) {
        return (
          <AddTriggerUI
            status="complete"
            args={{
              triggerType: "manual",
              triggerProperties: JSON.stringify({
                manual: "true",
              }),
            }}
            respond={undefined}
            result={args.result as SuggestionResult}
          />
        );
      }

      return (
        <AddTriggerUI
          status="executing"
          args={{
            triggerType: "manual",
            triggerProperties: JSON.stringify({
              manual: "true",
            }),
          }}
          respond={args.respond}
          result={undefined}
        />
      );
    },
  });

  const { keys } = useAlertKeys();
  const possibleAlertProperties = useMemo(() => {
    if (!keys || keys.length === 0) {
      return ["source", "severity", "status", "message", "timestamp"];
    }
    return keys?.map((key) => key.split(".").pop());
  }, [keys]);

  useCopilotReadable({
    description: "Possible alert properties",
    value: possibleAlertProperties,
  });

  useCopilotAction({
    name: "addAlertTrigger",
    description:
      "Add an alert trigger to the workflow. There could be only one alert trigger in the workflow, if you need more combine them into one alert trigger.",
    parameters: [
      {
        name: "alertFilters",
        description: "The filters of the alert trigger",
        type: "object[]",
        required: true,
        attributes: [
          {
            name: "attribute",
            description: `One of alert properties`,
            type: "string",
            required: true,
          },
          {
            name: "value",
            description: "The value of the alert filter",
            type: "string",
            required: true,
          },
        ],
      },
    ],
    renderAndWaitForResponse: (args) => {
      if (args.status === "inProgress") {
        return <AddTriggerSkeleton />;
      }

      const argsToPass = {
        triggerType: "alert",
        triggerProperties: JSON.stringify({
          alert: args.args.alertFilters.reduce(
            (acc, filter) => {
              acc[filter.attribute] = filter.value;
              return acc;
            },
            {} as Record<string, string>
          ),
        }),
      };

      if (args.status === "complete" && "result" in args) {
        return AddTriggerUI({
          status: "complete",
          args: argsToPass,
          respond: undefined,
          result: args.result as SuggestionResult,
        });
      }

      return AddTriggerUI({
        status: "executing",
        args: argsToPass,
        respond: args.respond,
        result: undefined,
      });
    },
  });

  useCopilotAction({
    name: "addIntervalTrigger",
    description:
      "Add an interval trigger to the workflow. There could be only one interval trigger in the workflow.",
    parameters: [
      {
        name: "interval",
        description: "The interval of the interval trigger in seconds",
        type: "number",
        required: true,
      },
    ],
    renderAndWaitForResponse: (args) => {
      if (args.status === "inProgress") {
        return <AddTriggerSkeleton />;
      }

      const argsToPass = {
        triggerType: "interval",
        triggerProperties: JSON.stringify({ interval: args.args.interval }),
      };

      if (args.status === "complete" && "result" in args) {
        return (
          <AddTriggerUI
            status="complete"
            args={argsToPass}
            respond={undefined}
            result={args.result as SuggestionResult}
          />
        );
      }

      return (
        <AddTriggerUI
          status="executing"
          args={argsToPass}
          respond={args.respond}
          result={undefined}
        />
      );
    },
  });

  useCopilotAction({
    name: "addIncidentTrigger",
    description:
      "Add an incident trigger to the workflow. There could be only one incident trigger in the workflow.",
    parameters: [
      {
        name: "incidentEvents",
        description: `The events of the incident trigger, one of: ${IncidentEventEnum.options.map((o) => `"${o}"`).join(", ")}`,
        type: "string[]",
        required: true,
      },
    ],
    renderAndWaitForResponse: (args) => {
      if (args.status === "inProgress") {
        return <AddTriggerSkeleton />;
      }

      const argsToPass = {
        triggerType: "incident",
        triggerProperties: JSON.stringify({
          incident: { events: args.args.incidentEvents },
        }),
      };

      if (args.status === "complete" && "result" in args) {
        return (
          <AddTriggerUI
            status="complete"
            args={argsToPass}
            respond={undefined}
            result={args.result as SuggestionResult}
          />
        );
      }

      return (
        <AddTriggerUI
          status="executing"
          args={argsToPass}
          respond={args.respond}
          result={undefined}
        />
      );
    },
  });

  function getActionStepFromCopilotAction(args: {
    actionId: string;
    actionType: string;
    actionName: string;
    providerName: string;
    withActionParams: { name: string; value: string }[];
  }) {
    const template = steps.find(
      (step): step is V2ActionStep =>
        step.type === args.actionType &&
        step.componentType === "task" &&
        "actionParams" in step.properties
    );
    if (!template) {
      return null;
    }
    const action: V2ActionStep = {
      ...template,
      id: args.actionId,
      name: args.actionName,
      properties: {
        ...template.properties,
        with: args.withActionParams.reduce(
          (acc, param) => {
            acc[param.name] = param.value;
            return acc;
          },
          {} as Record<string, string>
        ),
      },
    };
    return V2ActionSchema.parse(action);
  }

  useCopilotAction({
    name: "addAction",
    description:
      "Add an action to the workflow. Actions are sending notifications to a provider.",
    parameters: [
      {
        name: "withActionParams",
        description: "The parameters of the action to add",
        type: "object[]",
        required: true,
        attributes: [
          {
            name: "name",
            description: "The name of the action parameter",
            type: "string",
            required: true,
          },
          {
            name: "value",
            description: "The value of the action parameter",
            type: "string",
            required: true,
          },
        ],
      },
      {
        name: "actionId",
        description: "The id of the action to add",
        type: "string",
        required: true,
      },
      {
        name: "actionType",
        description: "The type of the action to add",
        type: "string",
        required: true,
      },
      {
        name: "actionName",
        description: "The kebab-case name of the action to add",
        type: "string",
        required: true,
      },
      {
        name: "providerName",
        description: "The name of the provider to add",
        type: "string",
        required: true,
      },
      {
        name: "addAfterEdgeId",
        description:
          "The id of the edge to add the action after. If you're adding action in condition branch, make sure the edge id ends with '-true' or '-false' according to the desired branch.",
        type: "string",
        required: true,
      },
    ],
    renderAndWaitForResponse: ({ status, args, respond, result }) => {
      if (status === "inProgress") {
        return <AddTriggerSkeleton />;
      }
      const action = getActionStepFromCopilotAction(args);
      if (!action) {
        respond?.({
          status: "error",
          error: "Action definition is invalid",
        });
        return <div>Action definition is invalid</div>;
      }

      return (
        <AddStepUI
          status={status}
          step={action}
          addAfterEdgeId={args.addAfterEdgeId}
          result={result}
          respond={respond}
        />
      );
    },
  });

  function getStepStepFromCopilotAction(args: {
    stepId: string;
    stepType: string;
    stepName: string;
    providerName: string;
    withStepParams: { name: string; value: string }[];
  }) {
    const template = steps.find(
      (step): step is V2StepStep => step.type === args.stepType
    );
    if (!template) {
      return null;
    }

    const step: V2StepStep = {
      ...template,
      id: args.stepId,
      name: args.stepName,
      properties: {
        ...template.properties,
        with: args.withStepParams.reduce(
          (acc, param) => {
            acc[param.name] = param.value;
            return acc;
          },
          {} as Record<string, string>
        ),
      },
    };
    return V2StepStepSchema.parse(step);
  }

  useCopilotAction({
    name: "addStep",
    description:
      "Add a step to the workflow. Steps are fetching data from a provider.",
    parameters: [
      {
        name: "withStepParams",
        description: "The parameters of the step to add",
        type: "object[]",
        required: true,
        attributes: [
          {
            name: "name",
            description: "The name of the step parameter",
            type: "string",
            required: true,
          },
          {
            name: "value",
            description: "The value of the step parameter",
            type: "string",
            required: true,
          },
        ],
      },
      {
        name: "stepId",
        description: "The id of the step to add",
        type: "string",
        required: true,
      },
      {
        name: "stepType",
        description: "The type of the step to add, should start with 'step-'",
        type: "string",
        required: true,
      },
      {
        name: "stepName",
        description: "The kebab-case name of the step to add",
        type: "string",
        required: true,
      },
      {
        name: "providerName",
        description: "The name of the provider to add",
        type: "string",
        required: true,
      },
      {
        name: "addAfterEdgeId",
        description: "The id of the edge to add the action after",
        type: "string",
        required: true,
      },
    ],
    renderAndWaitForResponse: ({ status, args, respond, result }) => {
      if (status === "inProgress") {
        return <AddTriggerSkeleton />;
      }
      const step = getStepStepFromCopilotAction(args);
      if (!step) {
        respond?.({
          status: "error",
          error: "Step definition is invalid",
        });
        return <div>Step definition is invalid</div>;
      }

      return (
        <AddStepUI
          status={status}
          step={step}
          result={result}
          addAfterEdgeId={args.addAfterEdgeId}
          respond={respond}
        />
      );
    },
  });

  function getConditionStepFromCopilotAction(args: {
    conditionId: string;
    conditionType: string;
    conditionName: string;
    conditionValue: string;
    compareToValue: string;
  }) {
    const template = steps.find(
      (step): step is V2StepCondition => step.type === args.conditionType
    );
    if (!template) {
      throw new Error("Condition type is invalid");
    }

    const condition: V2StepCondition = {
      ...template,
      id: args.conditionId,
      name: args.conditionName,
      properties: {
        ...template.properties,
        value: args.conditionValue,
        compare_to: args.compareToValue,
      },
    };
    return V2StepConditionSchema.parse(condition);
  }

  useCopilotAction({
    name: "addCondition",
    description: "Add a condition to the workflow.",
    parameters: [
      {
        name: "conditionId",
        description: "The id of the condition to add",
        type: "string",
        required: true,
      },
      {
        name: "conditionType",
        description:
          "The type of the condition to add. One of: 'condition-assert', 'condition-threshold'",
        type: "string",
        required: true,
      },
      {
        name: "conditionName",
        description: "The kebab-case name of the condition to add",
        type: "string",
        required: true,
      },
      {
        name: "conditionValue",
        description: "The value of the condition to add",
        type: "string",
        required: true,
      },
      {
        name: "compareToValue",
        description: "The value to compare the condition to",
        type: "string",
        required: true,
      },
      {
        name: "addAfterEdgeId",
        description: "The id of the edge to add the condition after",
        type: "string",
        required: true,
      },
    ],
    renderAndWaitForResponse: ({ status, args, respond, result }) => {
      if (status === "inProgress") {
        return <AddTriggerSkeleton />;
      }
      try {
        const condition = getConditionStepFromCopilotAction(args);
        if (!condition) {
          respond?.({
            status: "error",
            error: "Condition definition is invalid",
            errorDetail: "Condition type is invalid",
          });
          return <div>Condition definition is invalid</div>;
        }
        return (
          <AddStepUI
            status={status}
            step={condition}
            result={result}
            addAfterEdgeId={args.addAfterEdgeId}
            respond={respond}
          />
        );
      } catch (e) {
        respond?.({ status: "error", error: e });
        return <div>Failed to add condition {e?.message}</div>;
      }
    },
  });
  // const testStep = useTestStep();

  // TODO: add this action
  // useCopilotAction({
  //   name: "testRunStep",
  //   description: "Test run a step with given parameters",
  //   parameters: [
  //     {
  //       name: "providerId",
  //       description: "The id of the provider to test",
  //       type: "string",
  //       required: true,
  //     },
  //     {
  //       name: "providerType",
  //       description: "The type of the provider to test",
  //       type: "string",
  //       required: true,
  //     },
  //     {
  //       name: "stepType",
  //       description: "The type of the step to test: 'action' or 'step'",
  //       type: "string",
  //       required: true,
  //     },
  //     {
  //       name: "stepParams",
  //       description: "The parameters of the step to test",
  //       type: "object[]",
  //       required: true,
  //     },
  //   ],
  //   render: ({
  //     status,
  //     args: { providerId, stepParams, stepType, providerType },
  //     result,
  //   }) => {
  //     if (status === "inProgress") {
  //       return <div>Loading...</div>;
  //     }
  //     const step = steps?.find((step: any) => step.type === stepType) as V2Step;
  //     if (!step) {
  //       return <div>Step not found</div>;
  //     }
  //     const method = stepType === "action" ? "_notify" : "_query";
  //     try {
  //       const result = await testStep(
  //         {
  //           provider_id: providerId,
  //           provider_type: providerType,
  //         },
  //         method,
  //         stepParams
  //       );
  //       return <div>{JSON.stringify(result, null, 2)}</div>;
  //     } catch (e) {
  //       return <div>Failed to test step: {e.toString()}</div>;
  //     }
  //   },
  // });

  const [debugInfoVisible, setDebugInfoVisible] = useState(false);
  const chatInstructions = useMemo(() => {
    return (
      GENERAL_INSTRUCTIONS +
      `Here is the list of providers that are installed: ${installedProviders.map((p) => `type: ${p.type}, id: ${p.id}`).join(", ")}. If you you need to use a provider that is not installed, add step, but mention to user that you need to add the provider first.` +
      "Then asked to create a complete workflow, you break down the workflow into steps, outline the steps, show them to user, and then iterate over the steps one by one, generate step definition, show it to user to decide if they want to add them to the workflow."
    );
  }, [installedProviders]);

  return (
    <div
      className="flex flex-col h-full max-h-screen grow-0 overflow-auto"
      style={
        {
          "--copilot-kit-primary-color":
            "rgb(249 115 22 / var(--tw-bg-opacity))",
        } as CopilotKitCSSProperties
      }
    >
      {/* Debug info */}
      {WF_DEBUG_INFO && (
        <div className="">
          <div className="flex">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setMessages([])}
            >
              Reset
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setDebugInfoVisible(!debugInfoVisible)}
            >
              {debugInfoVisible ? "Hide" : "Show debug info"}
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={async () => {
                try {
                  const step = steps.find(
                    (step) => step.type === "step-python"
                  ) as V2StepStep;
                  if (!step) {
                    return;
                  }
                  // Generate a step definition of a python step that returns a list of 5 random cheer-up messages as a JSON object, allowed keys are: ${step.properties.stepParams?.join(", ") ?? "none"}
                  const definition = await generateStepDefinition({
                    name: "python-step",
                    stepType: step.type,
                    stepProperties: { ...step.properties },
                    aim: "This step should return random of five cheer-up messages (generate a list of 5 messages and hardcode them)",
                  });
                  console.log("!!!response", definition);
                } catch (e) {
                  console.error(e);
                }
              }}
            >
              Generate Example Definition
            </Button>
          </div>
          {debugInfoVisible && (
            <>
              <pre>{JSON.stringify(definition.value, null, 2)}</pre>
              <pre>selectedNode={JSON.stringify(selectedNode, null, 2)}</pre>
              <pre>selectedEdge={JSON.stringify(selectedEdge, null, 2)}</pre>
            </>
          )}
        </div>
      )}
      <CopilotChat
        instructions={chatInstructions}
        labels={{
          title: "Workflow Builder",
          initial: "What can I help you automate?",
          placeholder:
            "For example: For each alert about CPU > 80%, send a slack message to the channel #alerts",
        }}
        className="h-full flex-1"
      />
    </div>
  );
}

type BuilderChatSafeProps = Omit<BuilderChatProps, "definition"> & {
  definition: DefinitionV2 | null;
};

export function BuilderChatSafe({
  definition,
  ...props
}: BuilderChatSafeProps) {
  const { data: config } = useConfig();

  // If AI is not enabled, return null to collapse the chat section
  if (!config?.OPEN_AI_API_KEY_SET) {
    return (
      <div className="flex flex-col items-center justify-center h-full relative">
        <Image
          src={BuilderChatPlaceholder}
          alt="Workflow AI Assistant"
          width={400}
          height={895}
          className="w-full h-full object-cover object-top max-w-[500px] mx-auto absolute inset-0"
        />
        <div className="w-full h-full absolute inset-0 bg-white/80" />
        <div className="flex flex-col items-center justify-center h-full z-10">
          <div className="flex flex-col items-center justify-center bg-[radial-gradient(circle,white_50%,transparent)] p-8 rounded-lg aspect-square">
            <SparklesIcon className="size-10 text-orange-500" />
            <Title>AI is disabled</Title>
            <Text>Contact us to enable AI for you.</Text>
            <Link
              href="https://slack.keephq.dev/"
              target="_blank"
              rel="noopener noreferrer"
            >
              Contact us
            </Link>
          </div>
        </div>
      </div>
    );
  }

  if (definition == null) {
    return null;
  }

  return <BuilderChat definition={definition} {...props} />;
}
