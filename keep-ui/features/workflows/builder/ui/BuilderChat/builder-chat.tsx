import { useMemo, useState } from "react";
import { Provider } from "@/app/(keep)/providers/providers";
import {
  V2Step,
  V2Properties,
  FlowNode,
  ToolboxConfiguration,
} from "@/entities/workflows/model/types";
import { CopilotChat, CopilotKitCSSProperties } from "@copilotkit/react-ui";
import { useWorkflowStore } from "@/entities/workflows";
import {
  useCopilotAction,
  useCopilotChat,
  useCopilotReadable,
} from "@copilotkit/react-core";
import { Button } from "@/components/ui";
import { generateStepDefinition } from "@/app/(keep)/workflows/builder/_actions/getStepJson";
import { GENERAL_INSTRUCTIONS } from "@/app/(keep)/workflows/builder/_constants";
import { showSuccessToast } from "@/shared/ui/utils/showSuccessToast";
import { WF_DEBUG_INFO } from "../debug-settings";
import { AddTriggerUI } from "./AddTriggerUI";
import { AddStepUI } from "./AddStepUI";
import "@copilotkit/react-ui/styles.css";
import "./chat.css";

export function BuilderChat({
  definition,
  installedProviders,
}: {
  definition: {
    value: {
      sequence: V2Step[];
      properties: V2Properties;
    };
    isValid?: boolean;
  };
  installedProviders: Provider[];
}) {
  const {
    nodes,
    toolboxConfiguration,
    addNodeBetween,
    selectedEdge,
    selectedNode,
    deleteNodes,
  } = useWorkflowStore();

  const steps = useMemo(() => {
    return toolboxConfiguration?.groups?.map((g) => g.steps).flat();
  }, [toolboxConfiguration]);

  useCopilotReadable(
    {
      description: "Current nodes representing the workflow",
      value: nodes,
      convert: (description, nodes: FlowNode[]) => {
        return JSON.stringify(
          nodes.map((n) => ({ id: n.id, data: n.data })),
          null,
          2
        );
      },
    },
    [nodes]
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
              `${step.name}, properties: ${JSON.stringify(step.properties)}`
            );
          });
        });
        return result.join("\n");
      },
    },
    [steps]
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
        description: "The type of step to add",
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
    handler: ({ stepId }: { stepId: string }) => {
      // TODO: nice UI for this
      if (confirm(`Are you sure you want to remove ${stepId} step?`)) {
        deleteNodes(stepId);
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
    handler: ({ triggerNodeId }: { triggerNodeId: string }) => {
      // TODO: nice UI for this
      if (
        confirm(`Are you sure you want to remove ${triggerNodeId} trigger?`)
      ) {
        deleteNodes(triggerNodeId);
      }
    },
  });

  // TODO: simplify this action, e.g. params: componentType, name, properties
  useCopilotAction(
    {
      name: "generateStepDefinition",
      description: "Generate a workflow step definition",
      parameters: [
        {
          name: "stepType",
          description: "The type of step to add",
          type: "string",
          required: true,
        },
        {
          name: "name",
          description: "The short name of the step",
          type: "string",
          required: true,
        },
        {
          name: "aim",
          description:
            "The detailed description of the step's purpose and proposed solution",
          type: "string",
          required: true,
        },
      ],
      handler: async ({
        stepType,
        name,
        aim,
      }: {
        stepType: string;
        name: string;
        aim: string;
      }) => {
        const step = steps?.find(
          (step: any) => step.type === stepType
        ) as V2Step;
        if (!step) {
          return;
        }
        try {
          const stepDefinition = await generateStepDefinition({
            name,
            stepType,
            stepProperties: { ...step.properties },
            aim,
          });
          return {
            ...step,
            name: name ?? step.name,
            properties: {
              ...step.properties,
              with: stepDefinition,
            },
          };
        } catch (e) {
          console.error(e);
          return;
        }
      },
    },
    [steps]
  );

  useCopilotAction(
    {
      name: "addTrigger",
      description: "Add a trigger to the workflow",
      parameters: [
        {
          name: "triggerType",
          description:
            "The type of trigger to generate. One of: manual, alert, incident, or interval.",
          type: "string",
          required: true,
        },
        {
          name: "triggerProperties",
          description: "The properties of the trigger",
          type: "string",
          required: true,
        },
      ],
      renderAndWaitForResponse: (args) => {
        if (args.status === "inProgress") {
          return <div>Loading...</div>;
        }
        return AddTriggerUI(args);
      },
    },
    [steps]
  );

  useCopilotAction(
    {
      name: "addStep",
      description:
        "Add a step to the workflow. After adding a step ensure you have the updated workflow definition.",
      parameters: [
        {
          name: "stepDefinitionJSON",
          description: "The step definition to add",
          type: "string",
          required: true,
        },
        {
          name: "addAfterNodeName",
          description:
            "The 'name' of the step to add the new step after, get it from the workflow definition. If workflow is empty, use 'trigger_end'.",
          type: "string",
          required: true,
        },
        {
          // TODO: replace with more accurate nodeOrEdgeId description
          name: "isStart",
          description: "Whether the step is the start of the workflow",
          type: "boolean",
          required: false,
        },
      ],
      renderAndWaitForResponse: (args) => {
        if (args.status === "inProgress") {
          return <div>Loading...</div>;
        }
        return AddStepUI(args);
      },
    },
    [steps, selectedNode, selectedEdge, addNodeBetween]
  );

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
                    (step: any) => step.type === "step-python"
                  ) as V2Step;
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
