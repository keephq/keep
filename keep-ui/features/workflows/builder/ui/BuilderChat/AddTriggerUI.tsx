import { useState, useMemo, useCallback, useEffect } from "react";
import { useWorkflowStore, V2StepTriggerSchema } from "@/entities/workflows";
import { WF_DEBUG_INFO } from "../debug-settings";
import { Button } from "@/components/ui";
import { getTriggerTemplate } from "@/features/workflows/builder/lib/utils";
import { DebugArgs } from "./debug-args";
import { DebugJSON } from "@/shared/ui";
import { StepPreview } from "./StepPreview";
import { SuggestionStatus } from "./SuggestionStatus";

/**
 * Get the definition of a trigger
 * @param triggerType - The type of trigger
 * @param triggerProperties - The properties of the trigger
 * @returns The definition of the trigger
 * @throws ZodError if the trigger type is not supported or triggerProperties are invalid
 */
function getTriggerDefinition(triggerType: string, triggerProperties: string) {
  const triggerTemplate = getTriggerTemplate(triggerType);

  // TODO: validate triggerProperties here or in addNodeBetween??
  const triggerDefinition = {
    ...triggerTemplate,
    properties: {
      ...triggerTemplate.properties,
      ...JSON.parse(triggerProperties),
    },
  };
  return V2StepTriggerSchema.parse(triggerDefinition);
}

type SuggestionStatus = "complete" | "error" | "declined";
type SuggestionResult = {
  status: SuggestionStatus;
  message: string;
  error?: any;
};

type AddTriggerUIProps =
  | {
      status: "complete";
      args: {
        triggerType?: string;
        triggerProperties?: string;
      };
      respond: undefined;
      result: SuggestionResult;
    }
  | {
      status: "executing";
      args: {
        triggerType?: string;
        triggerProperties?: string;
      };
      respond: ((response: SuggestionResult) => void) | undefined;
      result: undefined;
    };

export const AddTriggerUI = ({
  status,
  args,
  respond,
  result,
}: AddTriggerUIProps) => {
  const [isAddingTrigger, setIsAddingTrigger] = useState(false);
  const { nodes, addNodeBetween, getNextEdge } = useWorkflowStore();
  const { triggerType, triggerProperties } = args;

  console.log("AddTriggerUI", { status, args, respond, result });

  const triggerDefinition = useMemo(() => {
    if (!triggerType || !triggerProperties) {
      throw new Error("Trigger type or properties not provided");
    }
    try {
      return getTriggerDefinition(triggerType, triggerProperties);
    } catch (e) {
      respond?.({
        status: "error",
        error: e,
        message: "Error getting trigger definition",
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [triggerType, triggerProperties]);

  const handleAddTrigger = useCallback(() => {
    if (!triggerDefinition) {
      respond?.({
        status: "error",
        error: new Error("trigger definition not found"),
        message: "trigger definition not found",
      });
      return;
    }
    if (isAddingTrigger) {
      console.log("isAddingTrigger", isAddingTrigger);
      return;
    }
    setIsAddingTrigger(true);
    try {
      const nextEdge = getNextEdge("trigger_start");
      if (!nextEdge) {
        respond?.({
          status: "error",
          error: new Error("Can't find the edge to add the trigger after"),
          message: "Trigger not added due to error",
        });
        return;
      }
      try {
        addNodeBetween(nextEdge.id, triggerDefinition, "edge");
        respond?.({
          status: "complete",
          message: "Trigger added",
        });
      } catch (e) {
        respond?.({
          status: "error",
          error: e,
          message: "Error adding trigger",
        });
      }
    } catch (e) {
      console.error(e);
      respond?.({
        status: "error",
        error: e,
        message: "Error adding trigger",
      });
    }
    setIsAddingTrigger(false);
  }, [triggerDefinition, respond]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
        if (!triggerDefinition) {
          return;
        }
        handleAddTrigger();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [args, respond]);

  if (!triggerType || !triggerProperties) {
    respond?.({
      status: "error",
      error: new Error("Trigger type or properties not provided"),
      message: "Trigger type or properties not provided",
    });
    return <>Trigger type or properties not provided</>;
  }
  if (!triggerDefinition) {
    respond?.({
      status: "error",
      error: new Error("Trigger definition not found"),
      message: "Trigger definition not found",
    });
    return <>Trigger definition not found</>;
  }
  if (status === "complete") {
    return (
      <div className="flex flex-col gap-1">
        {WF_DEBUG_INFO && (
          <DebugArgs args={{ args, result, status }} nodes={nodes} />
        )}
        {WF_DEBUG_INFO && (
          <DebugJSON name="triggerDefinition" json={triggerDefinition} />
        )}
        <StepPreview step={triggerDefinition} />
        <SuggestionStatus status={result?.status} message={result?.message} />
      </div>
    );
  }
  return (
    <div>
      {WF_DEBUG_INFO && (
        <DebugArgs args={{ args, result, status }} nodes={nodes} />
      )}
      {WF_DEBUG_INFO && (
        <DebugJSON name="triggerDefinition" json={triggerDefinition} />
      )}
      <p>Do you want to add this trigger to the workflow?</p>
      <div className="flex flex-col gap-2">
        <StepPreview step={triggerDefinition} />
        <div className="flex gap-2">
          <Button
            variant="primary"
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              handleAddTrigger();
            }}
          >
            {isAddingTrigger ? "Adding..." : "Add (⌘+Enter)"}
          </Button>
          <Button
            variant="secondary"
            onClick={() =>
              respond?.({
                status: "declined",
                message: "Trigger suggestion declined",
              })
            }
          >
            No
          </Button>
        </div>
      </div>
    </div>
  );
};
