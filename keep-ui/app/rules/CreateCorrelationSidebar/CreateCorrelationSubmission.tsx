import { Button } from "@tremor/react";
import { useSearchParams } from "next/navigation";

export const CreateCorrelationSubmission = () => {
  const searchParams = useSearchParams();
  const isRuleBeingEdited = searchParams ? searchParams.get("id") : null;

  return (
    <div className="col-span-2 flex justify-end items-end">
      <div className="flex items-center gap-x-4">
        <Button type="button" variant="light" color="orange">
          Cancel
        </Button>
        <Button className="rounded-none" color="orange">
          {isRuleBeingEdited ? "Save correlation" : "Create correlation"}
        </Button>
      </div>
    </div>
  );
};
