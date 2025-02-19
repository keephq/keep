import { Button } from "@/components/ui";
import { useWorkflowStore, V2Step } from "@/entities/workflows";
import { WF_DEBUG_INFO } from "../debug-settings";
import { DebugArgs } from "./debug-args";
import { StepPreview } from "./StepPreview";
import { SuggestionResult, SuggestionStatus } from "./SuggestionStatus";
import clsx from "clsx";
import { DebugJSON } from "@/shared/ui";
import { useCallback } from "react";
import { triggerTypes } from "../../lib/utils";
import { Edge } from "@xyflow/react";

type AddStepUIProps =
  | {
      status: "complete";
      args: {
        stepDefinitionJSON?: string;
        addAfterNodeName?: string;
        addAfterEdgeId?: string;
        isStart?: boolean;
      };
      respond: undefined;
      result: SuggestionResult;
    }
  | {
      status: "executing";
      args: {
        stepDefinitionJSON?: string;
        addAfterNodeName?: string;
        addAfterEdgeId?: string;
        isStart?: boolean;
      };
      respond: (response: SuggestionResult) => void;
      result: undefined;
    };

function getComponentType(stepType: string) {
  if (stepType.startsWith("step-")) return "task";
  if (stepType.startsWith("action-")) return "task";
  if (stepType.startsWith("condition-")) return "switch";
  if (stepType === "foreach") return "container";
  if (triggerTypes.includes(stepType)) return "trigger";
  return "task";
}

function parseAndAutoCorrectStepDefinition(stepDefinitionJSON: string) {
  const step = JSON.parse(stepDefinitionJSON);
  return {
    ...step,
    componentType: getComponentType(step.type),
  };
}

export const AddStepUI = ({
  status,
  args,
  respond,
  result,
}: AddStepUIProps) => {
  const {
    definition,
    nodes,
    getNodeById,
    getNextEdge,
    addNodeBetween,
    getEdgeById,
  } = useWorkflowStore();
  let {
    stepDefinitionJSON,
    addAfterNodeName: addAfterNodeIdOrName,
    addAfterEdgeId,
    isStart,
  } = args;

  const addNodeAfterNode = useCallback(
    (
      nodeToAddAfterId: string,
      step: V2Step,
      isStart: boolean,
      respond: (response: any) => void,
      addAfterEdgeId?: string
    ) => {
      if (
        nodeToAddAfterId === "alert" ||
        nodeToAddAfterId === "incident" ||
        nodeToAddAfterId === "interval" ||
        nodeToAddAfterId === "manual"
      ) {
        nodeToAddAfterId = "trigger_end";
      }
      let node = getNodeById(isStart ? "trigger_end" : nodeToAddAfterId);
      if (!node) {
        const nodeByName = definition?.value.sequence.find(
          (s) => s.name === nodeToAddAfterId
        );
        if (nodeByName) {
          node = getNodeById(nodeByName.id);
        }
        if (!node) {
          respond?.({
            status: "error",
            error: new Error("Can't find the node to add the step after"),
            message: "Step not added due to error",
          });
          return;
        }
      }
      let nextEdge: Edge | null = null;
      if (addAfterEdgeId) {
        nextEdge = getEdgeById(addAfterEdgeId) ?? null;
      }
      if (!nextEdge) {
        nextEdge = getNextEdge(node.id) ?? null;
      }
      if (!nextEdge) {
        respond?.({
          status: "error",
          error: new Error("Can't find the edge to add the step after"),
          message: "Step not added due to error",
        });
        return;
      }
      try {
        addNodeBetween(nextEdge.id, step, "edge");
        respond?.({
          status: "complete",
          stepId: step.id,
          message: "Step added",
        });
      } catch (e) {
        respond?.({
          status: "error",
          error: e,
          message: "Step not added due to error",
        });
      }
    },
    [addNodeBetween, definition?.value.sequence, getNextEdge, getNodeById]
  );

  if (!stepDefinitionJSON) {
    return <div>Step definition not found</div>;
  }
  if (definition?.value.sequence.length === 0) {
    isStart = true;
  }
  let step = parseAndAutoCorrectStepDefinition(stepDefinitionJSON);

  if (status === "complete") {
    return (
      <div className="flex flex-col gap-1">
        {WF_DEBUG_INFO && (
          <DebugArgs args={{ isStart, addAfterNodeIdOrName }} nodes={nodes} />
        )}
        <StepPreview
          step={step}
          className={clsx(
            result?.status === "declined" ? "opacity-50" : "",
            result?.status === "error" ? "bg-red-100" : ""
          )}
        />
        <SuggestionStatus status={result?.status} message={result?.message} />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      <div>
        <div>
          Do you want to add this step after <b>{addAfterNodeIdOrName}</b>
          <pre>{step.name}</pre>
          {WF_DEBUG_INFO && (
            <DebugArgs args={{ isStart, addAfterNodeIdOrName }} nodes={nodes} />
          )}
          {WF_DEBUG_INFO && (
            <DebugJSON
              name="stepDefinitionJSON"
              json={JSON.parse(stepDefinitionJSON ?? "")}
            />
          )}
        </div>
        <StepPreview step={step} />
      </div>
      <div className="flex gap-2">
        <Button
          color="orange"
          variant="primary"
          onClick={async () => {
            try {
              addNodeAfterNode(
                addAfterNodeIdOrName ?? "",
                step,
                !!isStart,
                respond,
                addAfterEdgeId
              );
            } catch (e) {
              console.error(e);
              respond?.({
                status: "error",
                error: e,
                message: `Error adding step: ${e}`,
              });
            }
          }}
        >
          Add (⌘+Enter)
        </Button>
        <Button
          color="orange"
          variant="secondary"
          onClick={() =>
            respond?.({
              status: "declined",
              message: "Step suggestion declined",
            })
          }
        >
          No
        </Button>
      </div>
    </div>
  );
};
