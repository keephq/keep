import { Button } from "@tremor/react";
import { useSearchParams } from "next/navigation";
import { useFormContext } from "react-hook-form";
import { CorrelationForm } from ".";
import { AlertsFoundBadge } from "./AlertsFoundBadge";
import { AlertDto } from "@/app/(keep)/alerts/models";

type CorrelationSubmissionProps = {
  toggle: VoidFunction;
  timeframeInSeconds: number;
};

export const CorrelationSubmission = ({
  toggle,
  timeframeInSeconds,
}: CorrelationSubmissionProps) => {
  const {
    formState: { isValid },
  } = useFormContext<CorrelationForm>();

  const exceeds14Days = Math.floor(timeframeInSeconds / 86400) > 13;

  const searchParams = useSearchParams();
  const isRuleBeingEdited = searchParams ? searchParams.get("id") : null;

  return (
    <div className="xl:col-span-2 flex justify-between items-end">
      <div className="flex items-center gap-x-4">
        <Button type="button" variant="light" color="orange" onClick={toggle}>
          Cancel
        </Button>
        <Button
          className="rounded-none"
          color="orange"
          disabled={!isValid || exceeds14Days}
        >
          {isRuleBeingEdited ? "Save correlation" : "Create correlation"}
        </Button>
      </div>
    </div>
  );
};
