import { useMemo, useState } from "react";
import { Provider } from "@/shared/api/providers";
import {
  DefinitionV2,
  IncidentEvent,
  IncidentEventEnum,
  ToolboxConfiguration,
  V2ActionSchema,
  V2ActionStep,
  V2Step,
  V2StepCondition,
  V2StepConditionSchema,
  V2StepStep,
  V2StepStepSchema,
  V2StepTrigger,
  V2StepTriggerSchema,
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
import { Button } from "@/components/ui";
import { GENERAL_INSTRUCTIONS } from "@/features/workflows/ai-assistant/lib/constants";
import { showSuccessToast } from "@/shared/ui/utils/showSuccessToast";
import { WF_DEBUG_INFO } from "../../builder/ui/debug-settings";
import { AddTriggerUI } from "./AddTriggerUI";
import { SuggestionResult } from "./SuggestionStatus";
import { AddStepUI } from "./AddStepUI";
import { useAvailableAlertFields } from "@/entities/alerts/model";
import {
  getErrorMessage,
  getWorkflowSummaryForCopilot,
} from "@/features/workflows/ai-assistant/lib/utils";
import { AddTriggerOrStepSkeleton } from "@/features/workflows/ai-assistant/ui/AddTriggerOrStepSkeleton";
import { foreachTemplate, getTriggerTemplate } from "../../builder/lib/utils";
import "@copilotkit/react-ui/styles.css";
import "./chat.css";
export interface WorkflowBuilderChatProps {
  definition: DefinitionV2;
  installedProviders: Provider[];
}

export function WorkflowBuilderChat({
  definition,
  installedProviders,
}: WorkflowBuilderChatProps) {
  const {
    nodes,
    edges,
    toolboxConfiguration,
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
      // TODO: nice UI for this
      if (confirm(`Are you sure you want to remove ${stepId} step?`)) {
        try {
          const deletedNodeIds = deleteNodes(stepId);
          if (deletedNodeIds.length > 0) {
            respond?.("Step removed");
            return <p>Step {stepId} removed</p>;
          } else {
            respond?.("Step removal failed");
            return <p>Step removal failed</p>;
          }
        } catch (e) {
          respond?.({
            status: "error",
            message: getErrorMessage(e, "Step removal failed"),
          });
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

      // TODO: nice UI for this
      if (
        confirm(`Are you sure you want to remove ${triggerNodeId} trigger?`)
      ) {
        try {
          const deletedNodeIds = deleteNodes(triggerNodeId);
          if (deletedNodeIds.length > 0) {
            respond?.("Trigger removed");
            return <p>Trigger {triggerNodeId} removed</p>;
          } else {
            respond?.("Trigger removal failed");
            return <p>Trigger removal failed</p>;
          }
        } catch (e) {
          respond?.({
            status: "error",
            message: getErrorMessage(e, "Trigger removal failed"),
          });
          return <p>Trigger removal failed</p>;
        }
      } else {
        respond?.("User cancelled the trigger removal");
        return <p>Trigger removal cancelled</p>;
      }
    },
  });

  /**
   * Get the definition of a trigger
   * @param triggerType - The type of trigger
   * @param triggerProperties - The properties of the trigger
   * @returns The definition of the trigger
   * @throws ZodError if the trigger type is not supported or triggerProperties are invalid
   */
  function getTriggerDefinitionFromCopilotAction(
    triggerType: string,
    triggerProperties: V2StepTrigger["properties"]
  ) {
    const triggerTemplate = getTriggerTemplate(triggerType);

    const triggerDefinition = {
      ...triggerTemplate,
      properties: {
        ...triggerTemplate.properties,
        ...triggerProperties,
      },
    };
    return V2StepTriggerSchema.parse(triggerDefinition);
  }

  useCopilotAction({
    name: "addManualTrigger",
    description:
      "Add a manual trigger to the workflow. There could be only one manual trigger in the workflow.",
    parameters: [],
    renderAndWaitForResponse: (args) => {
      if (args.status === "inProgress") {
        return <AddTriggerOrStepSkeleton />;
      }

      const trigger = getTriggerDefinitionFromCopilotAction("manual", {
        manual: "true",
      });

      if (args.status === "complete" && "result" in args) {
        return (
          <AddTriggerUI
            status="complete"
            trigger={trigger}
            respond={undefined}
            result={args.result as SuggestionResult}
          />
        );
      }

      return (
        <AddTriggerUI
          status="executing"
          trigger={trigger}
          respond={args.respond}
          result={undefined}
        />
      );
    },
  });

  const { fields } = useAvailableAlertFields();
  const possibleAlertProperties = useMemo(() => {
    if (!fields || fields.length === 0) {
      return ["source", "severity", "status", "message", "timestamp"];
    }
    return fields?.map((field) => field.split(".").pop());
  }, [fields]);

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
        return <AddTriggerOrStepSkeleton />;
      }

      const properties = {
        alert: args.args.alertFilters.reduce(
          (acc, filter) => {
            acc[filter.attribute] = filter.value;
            return acc;
          },
          {} as Record<string, string>
        ),
      };

      const trigger = getTriggerDefinitionFromCopilotAction(
        "alert",
        properties
      );

      if (args.status === "complete" && "result" in args) {
        return (
          <AddTriggerUI
            status="complete"
            trigger={trigger}
            respond={undefined}
            result={args.result as SuggestionResult}
          />
        );
      }

      return (
        <AddTriggerUI
          status="executing"
          trigger={trigger}
          respond={args.respond}
          result={undefined}
        />
      );
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
        return <AddTriggerOrStepSkeleton />;
      }

      const properties = {
        interval: args.args.interval,
      };

      const trigger = getTriggerDefinitionFromCopilotAction(
        "interval",
        properties
      );

      if (args.status === "complete" && "result" in args) {
        return (
          <AddTriggerUI
            status="complete"
            trigger={trigger}
            respond={undefined}
            result={args.result as SuggestionResult}
          />
        );
      }

      return (
        <AddTriggerUI
          status="executing"
          trigger={trigger}
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
        return <AddTriggerOrStepSkeleton />;
      }

      const properties = {
        incident: {
          events: args.args.incidentEvents as IncidentEvent[],
        },
      };

      const trigger = getTriggerDefinitionFromCopilotAction(
        "incident",
        properties
      );

      if (args.status === "complete" && "result" in args) {
        return (
          <AddTriggerUI
            status="complete"
            trigger={trigger}
            respond={undefined}
            result={args.result as SuggestionResult}
          />
        );
      }

      return (
        <AddTriggerUI
          status="executing"
          trigger={trigger}
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
        name: "addBeforeNodeId",
        description: `The id of the node to add the action before. For workflows with no steps, should be 'end'. Cannot be a node with componentType: 'trigger'. If adding to a condition branch, search for node id:
- Must end with '__empty_true' for true branch
- Must end with '__empty_false' for false branch
Example: 'node_123__empty_true'`,
        type: "string",
        required: true,
      },
    ],
    renderAndWaitForResponse: ({ status, args, respond, result }) => {
      if (status === "inProgress") {
        return <AddTriggerOrStepSkeleton />;
      }
      const action = getActionStepFromCopilotAction(args);
      if (!action) {
        respond?.({
          status: "error",
          error: "Action definition is invalid",
        });
        return <div>Action definition is invalid</div>;
      }

      if (status === "complete") {
        return (
          <AddStepUI
            status={status}
            step={action}
            addBeforeNodeId={args.addBeforeNodeId}
            result={result}
            respond={undefined}
          />
        );
      }

      return (
        <AddStepUI
          status={status}
          step={action}
          addBeforeNodeId={args.addBeforeNodeId}
          result={undefined}
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
        name: "addBeforeNodeId",
        description: `The id of the node to add the step before. For workflows with no steps, should be 'end'. Cannot be a node with componentType: 'trigger'. If adding to a condition branch, search for node id:
- Must end with '__empty_true' for true branch
- Must end with '__empty_false' for false branch
Example: 'node_123__empty_true'`,
        type: "string",
        required: true,
      },
    ],
    renderAndWaitForResponse: ({ status, args, respond, result }) => {
      if (status === "inProgress") {
        return <AddTriggerOrStepSkeleton />;
      }
      const step = getStepStepFromCopilotAction(args);
      if (!step) {
        respond?.({
          status: "error",
          error: "Step definition is invalid",
        });
        return <div>Step definition is invalid</div>;
      }

      if (status === "complete") {
        return (
          <AddStepUI
            status={status}
            step={step}
            addBeforeNodeId={args.addBeforeNodeId}
            result={result}
            respond={undefined}
          />
        );
      }

      return (
        <AddStepUI
          status={status}
          step={step}
          result={undefined}
          addBeforeNodeId={args.addBeforeNodeId}
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
        name: "addBeforeNodeId",
        description: `The id of the node to add the condition before. For workflows with no steps, should be 'end'. Cannot be a node with componentType: 'trigger'. If adding to a condition branch, search for node id:
- Must end with '__empty_true' for true branch
- Must end with '__empty_false' for false branch
Example: 'node_123__empty_true'`,
        type: "string",
        required: true,
      },
    ],
    renderAndWaitForResponse: ({ status, args, respond, result }) => {
      if (status === "inProgress") {
        return <AddTriggerOrStepSkeleton />;
      }
      try {
        const condition = getConditionStepFromCopilotAction(args);
        if (!condition) {
          respond?.({
            status: "error",
            message: "Condition definition is invalid",
          });
          return <div>Condition definition is invalid</div>;
        }
        if (status === "complete") {
          return (
            <AddStepUI
              status={status}
              step={condition}
              result={result}
              addBeforeNodeId={args.addBeforeNodeId}
              respond={respond}
            />
          );
        }
        return (
          <AddStepUI
            status={status}
            step={condition}
            result={undefined}
            addBeforeNodeId={args.addBeforeNodeId}
            respond={respond}
          />
        );
      } catch (e: any) {
        respond?.({ status: "error", message: getErrorMessage(e) });
        return <div>Failed to add condition {e?.message}</div>;
      }
    },
  });

  function getForeachStepFromCopilotAction(args: {
    foreachName: string;
    value: string;
    addBeforeNodeId: string;
  }) {
    return {
      ...foreachTemplate,
      name: args.foreachName,
      id: `foreach_${args.foreachName}`,
      properties: {
        ...foreachTemplate.properties,
        value: args.value,
      },
    };
  }

  useCopilotAction({
    name: "addForeach",
    description: "Add a foreach loop to the workflow.",
    parameters: [
      {
        name: "foreachName",
        description: "The kebab-case name of the foreach to add",
        type: "string",
        required: true,
      },
      {
        name: "value",
        description:
          "The value to iterate over. Could refer to results from previous steps: '{{ steps.<stepId>.results }}'.",
        type: "string",
        required: true,
      },
      {
        name: "addBeforeNodeId",
        description: `The id of the node to add the foreach before. For workflows with no steps, should be 'end'. Cannot be a node with componentType: 'trigger'. If adding to a condition branch, search for node id:
- Must end with '__empty_true' for true branch
- Must end with '__empty_false' for false branch
Example: 'node_123__empty_true'`,
        type: "string",
        required: true,
      },
    ],
    renderAndWaitForResponse: ({ status, args, respond, result }) => {
      if (status === "inProgress") {
        return <AddTriggerOrStepSkeleton />;
      }
      const foreach = getForeachStepFromCopilotAction(args);

      if (status === "complete") {
        return (
          <AddStepUI
            status={status}
            step={foreach}
            addBeforeNodeId={args.addBeforeNodeId}
            result={result}
            respond={undefined}
          />
        );
      }
      return (
        <AddStepUI
          status={status}
          step={foreach}
          addBeforeNodeId={args.addBeforeNodeId}
          result={undefined}
          respond={respond}
        />
      );
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
  const chatInstructions =
    GENERAL_INSTRUCTIONS +
    `If you you need to use a provider that is not installed, add step, but mention to user that you need to add the provider first.
      Then asked to create a complete workflow, you break down the workflow into steps, outline the steps, show them to user, and then iterate over the steps one by one, generate step definition, show it to user to decide if they want to add them to the workflow.`;

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
              size="xs"
              onClick={() => setMessages([])}
            >
              Reset
            </Button>
            <Button
              variant="secondary"
              size="xs"
              onClick={() => setDebugInfoVisible(!debugInfoVisible)}
            >
              {debugInfoVisible ? "Hide definition" : "Show definition"}
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
