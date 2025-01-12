import { useMemo, useState } from "react";
import { Provider } from "../../providers/providers";
import { V2Step, V2Properties } from "./types";
import { CopilotChat, CopilotKitCSSProperties } from "@copilotkit/react-ui";
import useStore from "./builder-store";
import {
  useCopilotAction,
  useCopilotChat,
  useCopilotReadable,
} from "@copilotkit/react-core";
import { Button } from "@/components/ui";
import Image from "next/image";
import "@copilotkit/react-ui/styles.css";
import "./chat.css";
import { generateStepDefinition } from "./_actions/getStepJson";
import { AFTER_TRIGGER_ID, GENERAL_INSTRUCTIONS } from "./_constants";
import { CheckCircleIcon } from "@heroicons/react/20/solid";
import { showSuccessToast } from "@/shared/ui/utils/showSuccessToast";

function IconUrlProvider(data: V2Step) {
  const { type } = data || {};
  if (type === "alert" || type === "workflow" || type === "trigger" || !type)
    return "/keep.png";
  if (type === "incident" || type === "workflow" || type === "trigger" || !type)
    return "/keep.png";
  return `/icons/${type
    ?.replace("step-", "")
    ?.replace("action-", "")
    ?.replace("__end", "")
    ?.replace("condition-", "")}-icon.png`;
}

const StepPreview = ({ step }: { step: V2Step }) => {
  const type = step?.type
    ?.replace("step-", "")
    ?.replace("action-", "")
    ?.replace("condition-", "")
    ?.replace("__end", "")
    ?.replace("trigger_", "");
  return (
    <div className="max-w-[250px] flex shadow-md rounded-md bg-white border-2 border-stone-400 p-2 flex-1 flex-row items-center justify-between gap-2 flex-wrap">
      {!!type && !["interval", "manual"].includes(type) && (
        <Image
          src={IconUrlProvider(step) || "/keep.png"}
          alt={step?.type}
          className="object-cover w-8 h-8 rounded-full bg-gray-100"
          width={32}
          height={32}
        />
      )}
      <div className="flex-1 flex-col gap-2 flex-wrap truncate">
        <div className="text-lg font-bold truncate">{step.name}</div>
        <div className="text-gray-500 truncate">{type}</div>
      </div>
    </div>
  );
};

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
  console.log("BuilderChat", { definition, installedProviders });
  const {
    getNextEdge,
    toolboxConfiguration,
    addNodeBetween,
    selectedEdge,
    selectedNode,
    deleteNodes,
    getNodeById,
  } = useStore();

  const steps = useMemo(() => {
    return toolboxConfiguration?.groups?.map((g) => g.steps).flat();
  }, [toolboxConfiguration]);

  useCopilotReadable(
    {
      description: "Current workflow definition",
      value: definition.value,
    },
    [definition]
  );

  useCopilotReadable(
    {
      description: "These are steps that you can add to the workflow",
      value: steps,
      convert: (description, value) => {
        return value
          ?.map(
            (s) =>
              `${s.name} - ${s.type}, stepParams: ${s.properties?.stepParams?.join(", ") ?? "none"}, actionParams: ${s.properties?.actionParams?.join(", ") ?? "none"}`
          )
          ?.join(", ");
      },
    },
    [steps]
  );

  const { setMessages } = useCopilotChat();

  // const handleAddingStep = ({stepType,
  //   nodeOrEdgeId,
  //   after,
  //   isStart,
  //   name,
  //   aim,
  // }: {
  //   stepType: string;
  //   nodeOrEdgeId: string;
  //   after: boolean;
  //   isStart: boolean;
  //   name: string;
  //   aim: string;
  // }) => {
  //   const step = steps.find((step: any) => step.type === stepType) as V2Step;
  //   if (!step) {
  //     return;
  //   }
  //   const stepDefinition = generateStepDefinition(name, step, aim);
  // }

  const { v2Properties: properties, updateV2Properties: setProperties } =
    useStore();

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
    name: "removeStep",
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
      if (confirm(`Are you sure you want to remove ${stepId} step?`)) {
        deleteNodes(stepId);
      }
    },
  });

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
        const step = steps.find(
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
          name: "nodeIdOrName",
          description:
            "The 'id' or 'name' property of the step to add the step after, get it from the workflow definition. DO NOT USE the workflow id. If you don't know the id, update the workflow definition and try again.",
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
      renderAndWaitForResponse: ({ status, args, respond }) => {
        if (status === "inProgress") {
          return <div>Loading...</div>;
        }
        console.log("args=", args);
        const { stepDefinitionJSON, nodeIdOrName, isStart } = args;
        let step = JSON.parse(stepDefinitionJSON);
        let node = getNodeById(isStart ? "trigger_end" : nodeIdOrName);
        if (!node) {
          const nodeByName = definition.value.sequence.find(
            (s) => s.name === nodeIdOrName
          );
          if (nodeByName) {
            node = getNodeById(nodeByName.id);
          }
          if (!node) {
            respond?.("node not found");
            return (
              <>
                <code className="text-xs leading-none text-gray-500">
                  {JSON.stringify(args, null, 2)}
                </code>
                <code className="text-xs leading-none text-gray-500">
                  {JSON.stringify(definition.value, null, 2)}
                </code>
                <p className="text-sm text-red-500">Node not found</p>
              </>
            );
          }
        }
        if (status === "complete") {
          return (
            <div className="flex flex-col gap-1">
              <code>args={JSON.stringify(args, null, 2)}</code>
              <StepPreview step={step} />
              <p className="text-sm text-gray-500">
                <CheckCircleIcon className="w-4 h-4" /> Step added
              </p>
            </div>
          );
        }
        return (
          <div className="flex flex-col gap-2">
            <div>
              <div>
                Do you want to add this step after <b>{node.data.name}</b>
                <pre>{step.name}</pre>
                <code className="text-xs leading-none text-gray-500">
                  {stepDefinitionJSON}
                </code>
              </div>
              <StepPreview step={step} />
            </div>
            <div className="flex gap-2">
              <Button
                color="orange"
                variant="primary"
                onClick={async () => {
                  try {
                    const nextEdge = getNextEdge(node.id);
                    if (!nextEdge) {
                      respond?.("next edge not found");
                      return <></>;
                    }
                    addNodeBetween(nextEdge.id, step, "edge");
                    respond?.("step added");
                  } catch (e) {
                    console.error(e);
                    respond?.(`error adding step: ${e}`);
                  }
                }}
              >
                Add
              </Button>
              <Button
                color="orange"
                variant="secondary"
                onClick={() => respond?.("step not added")}
              >
                No
              </Button>
            </div>
          </div>
        );
      },
    },
    [steps, selectedNode, selectedEdge, addNodeBetween]
  );

  const [debugInfoVisible, setDebugInfoVisible] = useState(false);
  const chatInstructions = useMemo(() => {
    return (
      GENERAL_INSTRUCTIONS +
      `Here is the list of providers that are installed: ${installedProviders.map((p) => `type: ${p.type}, id: ${p.id}`).join(", ")}. If you you need to use a provider that is not installed, add step, but mention to user that you need to add the provider first.` +
      "Then asked to create a whole workflow, you break down the workflow into steps, outline the steps and show it to user, and then iterate over the steps, generate step definitions, show them to user for them to decide if they want to add them to the workflow."
    );
  }, [installedProviders]);

  return (
    <div
      className="flex flex-col h-full max-h-screen basis-[600px] grow-0 overflow-auto"
      style={
        {
          "--copilot-kit-primary-color":
            "rgb(249 115 22 / var(--tw-bg-opacity))",
        } as CopilotKitCSSProperties
      }
    >
      {/* Debug info */}
      <div className="">
        <div className="flex">
          <Button variant="secondary" size="sm" onClick={() => setMessages([])}>
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
      <CopilotChat instructions={chatInstructions} className="h-full flex-1" />
    </div>
  );
}
