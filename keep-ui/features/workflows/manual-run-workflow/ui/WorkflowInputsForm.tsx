import { WorkflowInput } from "@/entities/workflows/model/yaml.types";
import { WorkflowInputFields } from "@/entities/workflows/ui/WorkflowInputFields";
import { Button, Text } from "@tremor/react";
import { useEffect, useMemo, useState } from "react";

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

  useEffect(() => {
    // Initialize input values with defaults
    const initialValues: Record<string, any> = {};
    workflowInputs.forEach((input) => {
      initialValues[input.name] =
        input.default !== undefined ? input.default : "";
    });
    setInputValues(initialValues);
  }, [workflowInputs]);

  const enhancedInputs = useMemo(
    () =>
      workflowInputs.map((input) => {
        // Mark inputs without defaults as visually required
        if (input.default === undefined && !input.required) {
          return { ...input, visuallyRequired: true };
        }
        return input;
      }),
    [workflowInputs]
  );

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
      <Text className="font-bold">Inputs required to run the workflow</Text>
      <WorkflowInputFields
        workflowInputs={enhancedInputs}
        inputValues={inputValues}
        onInputChange={handleInputChange}
      />
      <div className="flex justify-end gap-2">
        <Button
          variant="secondary"
          onClick={onCancel}
          data-testid="wf-inputs-form-cancel"
        >
          Cancel
        </Button>
        <Button
          variant="primary"
          color="orange"
          type="submit"
          data-testid="wf-inputs-form-submit"
        >
          Run
        </Button>
      </div>
    </form>
  );
}
