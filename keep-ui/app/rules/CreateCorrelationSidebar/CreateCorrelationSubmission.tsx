import { Button } from "@tremor/react";

export const CreateCorrelationSubmission = () => {
  return (
    <div className="col-span-2 flex justify-end items-end">
      <div className="flex items-center gap-x-4">
        <Button type="button" variant="light" color="orange">
          Cancel
        </Button>
        <Button className="rounded-none" color="orange">
          Create Correlation
        </Button>
      </div>
    </div>
  );
};
