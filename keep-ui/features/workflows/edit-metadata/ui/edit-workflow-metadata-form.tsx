import { Button, Textarea, TextInput } from "@/components/ui";
import { WorkflowMetadata } from "@/entities/workflows";
import { Subtitle, Text } from "@tremor/react";
import { useState } from "react";

export function EditWorkflowMetadataForm({
  workflow,
  onCancel,
  onSubmit,
}: {
  workflow: WorkflowMetadata;
  onCancel: () => void;
  onSubmit: ({
    name,
    description,
  }: {
    name: string;
    description: string;
  }) => void;
}) {
  const [name, setName] = useState(workflow.name);
  const [description, setDescription] = useState(workflow.description);
  const isSubmitEnabled = !!name.trim() && !!description.trim();

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    onSubmit({ name: name.trim(), description: description.trim() });
  };

  return (
    <form className="py-2" onSubmit={handleSubmit}>
      <Subtitle>Workflow Metadata</Subtitle>
      <div className="mt-2.5">
        <Text className="mb-2">
          Name<span className="text-red-500 text-xs">*</span>
        </Text>
        <TextInput
          required
          placeholder="Workflow Name"
          value={name}
          onValueChange={setName}
        />
      </div>
      <div className="mt-2.5">
        <Text className="mb-2">Description</Text>
        <Textarea
          required
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
