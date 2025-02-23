import { Button } from "@/components/ui";
import { StepPreview } from "./StepPreview";
import { SuggestionResult, SuggestionStatus } from "./SuggestionStatus";
import clsx from "clsx";
import { V2Step } from "@/entities/workflows/model/types";
import { useWorkflowStore } from "@/entities/workflows";

type AddStepUIPropsCommon = {
  step: V2Step;
  addBeforeNodeId: string;
};

type AddStepUIPropsComplete = AddStepUIPropsCommon & {
  status: "complete";
  result: SuggestionResult;
  respond: undefined;
};

type AddStepUIPropsExecuting = AddStepUIPropsCommon & {
  status: "executing";
  result: undefined;
  respond: (response: SuggestionResult) => void;
};

type AddStepUIProps = AddStepUIPropsComplete | AddStepUIPropsExecuting;

export const AddStepUI = ({
  status,
  step,
  addBeforeNodeId,
  result,
  respond,
}: AddStepUIProps) => {
  const { addNodeBetween, setSelectedNode, getNodeById } = useWorkflowStore();

  const selectNode = () => {
    const node = getNodeById(addBeforeNodeId);
    if (node) {
      setSelectedNode(node.id);
    }
  };

  const onAdd = () => {
    try {
      addNodeBetween(addBeforeNodeId, step, "node");
      respond?.({
        status: "complete",
        message: "Step added",
      });
    } catch (e) {
      console.error("Step not added", e);
      respond?.({
        status: "error",
        error: e,
        message: "Step not added",
      });
    }
  };

  const onCancel = () => {
    respond?.({
      status: "complete",
      message: "User cancelled adding step",
    });
  };

  if (status === "complete") {
    return (
      <div className="flex flex-col gap-1 my-2">
        <div>
          Do you want to add this action before node {addBeforeNodeId} (
          <button className="text-blue-500" onClick={selectNode}>
            Select node
          </button>
          )?
        </div>
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
        {/* TODO: add the place where the action will be added in text */}
        <div>
          Do you want to add this action before node {addBeforeNodeId} (
          <button className="text-blue-500" onClick={selectNode}>
            Select node
          </button>
          )?
        </div>
        <div className="my-2">
          <StepPreview step={step} />
        </div>
      </div>
      <div className="flex gap-2">
        <Button color="orange" variant="primary" onClick={onAdd}>
          Add (⌘+Enter)
        </Button>
        <Button color="orange" variant="secondary" onClick={onCancel}>
          No
        </Button>
      </div>
    </div>
  );
};
