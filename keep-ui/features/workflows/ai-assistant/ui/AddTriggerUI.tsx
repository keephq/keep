import { useState, useCallback, useEffect } from "react";
import { useI18n } from "@/i18n/hooks/useI18n";
import { useWorkflowStore } from "@/entities/workflows";
import { Button } from "@/components/ui";
import { JsonCard } from "@/shared/ui";
import { StepPreview } from "./StepPreview";
import { SuggestionResult, SuggestionStatus } from "./SuggestionStatus";
import { getErrorMessage } from "../lib/utils";
import { V2StepTrigger } from "@/entities/workflows/model/types";
import { useConfig } from "@/utils/hooks/useConfig";

type AddTriggerUIPropsCommon = {
  trigger: V2StepTrigger;
};

type AddTriggerUIPropsComplete = AddTriggerUIPropsCommon & {
  status: "complete";
  result: SuggestionResult;
  respond: undefined;
};

type AddTriggerUIPropsExecuting = AddTriggerUIPropsCommon & {
  status: "executing";
  result: undefined;
  respond: ((response: SuggestionResult) => void) | undefined;
};

type AddTriggerUIProps = AddTriggerUIPropsComplete | AddTriggerUIPropsExecuting;

export const AddTriggerUI = ({
  status,
  trigger,
  respond,
  result,
}: AddTriggerUIProps) => {
  const { t } = useI18n();
  const [isAddingTrigger, setIsAddingTrigger] = useState(false);
  const { addNodeBetween, getNextEdge } = useWorkflowStore();
  const { data: config } = useConfig();

  const handleAddTrigger = useCallback(() => {
    if (isAddingTrigger) {
      return;
    }
    setIsAddingTrigger(true);
    try {
      const nextEdge = getNextEdge("trigger_start");
      if (!nextEdge) {
        respond?.({
          status: "error",
          message: t("workflows.aiAssistant.cantFindEdge"),
        });
        return;
      }
      try {
        addNodeBetween(nextEdge.id, trigger, "edge");
        respond?.({
          status: "complete",
          message: t("workflows.aiAssistant.triggerAdded"),
        });
      } catch (e) {
        respond?.({
          status: "error",
          message: getErrorMessage(e),
        });
      }
    } catch (e) {
      respond?.({
        status: "error",
        message: getErrorMessage(e),
      });
    }
    setIsAddingTrigger(false);
  }, [trigger, respond]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
        handleAddTrigger();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [respond]);

  if (status === "complete") {
    return (
      <div className="flex flex-col gap-1 my-2">
        {config?.KEEP_WORKFLOW_DEBUG && (
          <JsonCard title="trigger" json={trigger} />
        )}
        <p>{t("workflows.aiAssistant.confirmAddTrigger")}</p>
        <StepPreview step={trigger} />
        <SuggestionStatus status={result?.status} message={result?.message} />
      </div>
    );
  }
  return (
    <div>
      {config?.KEEP_WORKFLOW_DEBUG && (
        <JsonCard title="trigger" json={trigger} />
      )}
      <p>{t("workflows.aiAssistant.confirmAddTrigger")}</p>
      <div className="flex flex-col gap-2 my-2">
        <StepPreview step={trigger} />
        <div className="flex gap-2">
          <Button
            variant="primary"
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              handleAddTrigger();
            }}
          >
            {isAddingTrigger ? t("workflows.aiAssistant.adding") : t("workflows.aiAssistant.addTrigger")}
          </Button>
          <Button
            variant="secondary"
            onClick={() =>
              respond?.({
                status: "declined",
                message: t("workflows.aiAssistant.triggerSuggestionDeclined"),
              })
            }
          >
            {t("workflows.aiAssistant.no")}
          </Button>
        </div>
      </div>
    </div>
  );
};
