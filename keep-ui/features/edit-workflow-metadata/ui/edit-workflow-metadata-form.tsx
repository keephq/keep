import { Button, Textarea, TextInput } from "@/components/ui";
import { Workflow } from "@/shared/api/workflows";
import { Subtitle, Text } from "@tremor/react";
import { useState } from "react";

export function EditWorkflowMetadataForm({
  workflow,
  onCancel,
  onSubmit,
}: {
  workflow: Workflow;
  onCancel: () => void;
  onSubmit: (
    workflowId: string,
    { name, description }: { name: string; description: string }
  ) => void;
}) {
  const [name, setName] = useState(workflow.name);
  const [description, setDescription] = useState(workflow.description);
  const isSubmitEnabled = !!name && !!description;

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    onSubmit(workflow.id, { name, description });
  };

  return (
    <form className="py-2" onSubmit={handleSubmit}>
      <Subtitle>Workflow Metadata</Subtitle>
      <div className="mt-2.5">
        <Text className="mb-2">
          Name<span className="text-red-500 text-xs">*</span>
        </Text>
        <TextInput
          placeholder="Workflow Name"
          required={true}
          value={name}
          onValueChange={setName}
        />
      </div>
      <div className="mt-2.5">
        <Text className="mb-2">Description</Text>
        <Textarea
          placeholder="Workflow Description"
          value={description}
          onValueChange={setDescription}
        />
      </div>
      <div className="mt-auto pt-6 space-x-1 flex flex-row justify-end items-center">
        <Button color="orange" size="xs" variant="secondary" onClick={onCancel}>
          Cancel
        </Button>
        <Button
          disabled={!isSubmitEnabled}
          variant="primary"
          color="orange"
          size="xs"
          type="submit"
        >
          Update
        </Button>
      </div>
    </form>
  );
}
