import { useMemo, useState } from "react";
import { Provider } from "@/app/(keep)/providers/providers";
import {
  V2Step,
  FlowNode,
  ToolboxConfiguration,
  V2StepStep,
  DefinitionV2,
} from "@/entities/workflows/model/types";
import {
  CopilotChat,
  CopilotKitCSSProperties,
  useCopilotChatSuggestions,
} from "@copilotkit/react-ui";
import { useWorkflowStore } from "@/entities/workflows";
import {
  CopilotKit,
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
import { AddStepUI } from "./AddStepUI";
import "@copilotkit/react-ui/styles.css";
import "./chat.css";
import { useTestStep } from "../Editor/StepTest";
import { useConfig } from "@/utils/hooks/useConfig";
import { Title, Text } from "@tremor/react";
import { SparklesIcon } from "@heroicons/react/24/outline";
import BuilderChatPlaceholder from "./ai-workflow-placeholder.png";
import Image from "next/image";
import { Edge } from "@xyflow/react";

interface BuilderChatProps {
  definition: DefinitionV2;
  installedProviders: Provider[];
}

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

  // TODO: reduce the size of the nodes object, e.g. only id and data, or something like this
  useCopilotReadable(
    {
      description: "Current nodes representing the workflow",
      value: nodes,
      convert: (description, nodes: FlowNode[]) => {
        return JSON.stringify(
          nodes.map((n) => ({
            id: n.id,
            componentType: n.data.componentType,
            name: n.data.name,
          })),
          null,
          2
        );
      },
    },
    [nodes]
  );

  useCopilotReadable(
    {
      description: "Current edges representing the workflow",
      value: edges,
      convert: (description, edges: Edge[]) => {
        return JSON.stringify(
          edges.map((e) => ({ id: e.id, source: e.source, target: e.target })),
          null,
          2
        );
      },
    },
    [edges]
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
          description:
            "The type of step to add e.g. action-slack, step-python, condition-assert, etc",
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
        const step = steps?.find((step: any) => step.type === stepType);
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
          description:
            "The step definition to add, use the 'generateStepDefinition' action to generate a step definition.",
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
          name: "addAfterEdgeId",
          description:
            "If you want to add the step after specific edge, use the edgeId.",
          type: "string",
          required: false,
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

  const testStep = useTestStep();

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

  return (
    <CopilotKit showDevConsole={true} runtimeUrl="/api/copilotkit">
      <BuilderChat definition={definition} {...props} />
    </CopilotKit>
  );
}
