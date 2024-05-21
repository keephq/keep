import { Button } from "@tremor/react";
import { useSearchParams } from "next/navigation";
import { useFormContext } from "react-hook-form";
import { CorrelationForm } from ".";
import { AlertsFoundBadge } from "./AlertsFoundBadge";
import { AlertDto } from "app/alerts/models";

type CorrelationSubmissionProps = {
  toggle: VoidFunction;
  alertsFound: AlertDto[];
};

export const CorrelationSubmission = ({
  toggle,
  alertsFound,
}: CorrelationSubmissionProps) => {
  const {
    formState: { isValid },
  } = useFormContext<CorrelationForm>();

  const searchParams = useSearchParams();
  const isRuleBeingEdited = searchParams ? searchParams.get("id") : null;

  return (
    <div className="col-span-2 flex justify-between items-end">
      <div>
        <AlertsFoundBadge alertsFound={alertsFound} />
      </div>

      <div className="flex items-center gap-x-4">
        <Button type="button" variant="light" color="orange" onClick={toggle}>
          Cancel
        </Button>
        <Button
          className="rounded-none"
          color="orange"
          disabled={isValid === false}
        >
          {isRuleBeingEdited ? "Save correlation" : "Create correlation"}
        </Button>
      </div>
    </div>
  );
};
