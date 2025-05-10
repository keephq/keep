import { WorkflowInput } from "@/entities/workflows/model/yaml.schema";
import { WorkflowInputFields } from "@/entities/workflows/ui/WorkflowInputFields";
import { Button, Text } from "@tremor/react";
import { useState } from "react";

interface WorkflowInputsFormProps {
  workflowInputs: WorkflowInput[];
  onSubmit: (inputs: Record<string, any>) => void;
  onCancel: () => void;
}

export function WorkflowInputsForm({
  workflowInputs,
  onSubmit,
  onCancel,
}: WorkflowInputsFormProps) {
  const [inputValues, setInputValues] = useState<Record<string, any>>({});

  const handleInputChange = (name: string, value: any) => {
    setInputValues((prev) => ({
      ...prev,
      [name]: value,
    }));
  };

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    onSubmit(inputValues);
  };

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-2">
      <Text className="font-bold">
        Fill in the inputs required to run the workflow
      </Text>
      <WorkflowInputFields
        workflowInputs={workflowInputs}
        inputValues={inputValues}
        onInputChange={handleInputChange}
      />
      <div className="flex justify-end gap-2">
        <Button variant="secondary" onClick={onCancel}>
          Cancel
        </Button>
        <Button variant="primary" color="orange" type="submit">
          Run
        </Button>
      </div>
    </form>
  );
}
