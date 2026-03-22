import { Button, Textarea, TextInput } from "@/components/ui";
import { Workflow } from "@/shared/api/workflows";
import { Subtitle, Text } from "@tremor/react";
import { useState } from "react";
import { useI18n } from "@/i18n/hooks/useI18n";

export function EditWorkflowMetadataForm({
  workflow,
  onCancel,
  onSubmit,
}: {
  workflow: Pick<Workflow, "id" | "name" | "description">;
  onCancel: () => void;
  onSubmit: (
    workflowId: string,
    { name, description }: { name: string; description: string }
  ) => void;
}) {
  const { t } = useI18n();
  const [name, setName] = useState(workflow.name);
  const [description, setDescription] = useState(workflow.description);
  const isSubmitEnabled = !!name && !!description;

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    onSubmit(workflow.id, { name, description });
  };

  return (
    <form className="py-2" onSubmit={handleSubmit}>
      <Subtitle>{t("workflows.builder.workflowMetadata")}</Subtitle>
      <div className="mt-2.5">
        <Text className="mb-2">
          {t("common.labels.name")}<span className="text-red-500 text-xs">*</span>
        </Text>
        <TextInput
          placeholder={t("workflows.builder.workflowNamePlaceholder")}
          required={true}
          value={name}
          onValueChange={setName}
        />
      </div>
      <div className="mt-2.5">
        <Text className="mb-2">{t("common.labels.description")}</Text>
        <Textarea
          placeholder={t("workflows.builder.workflowDescriptionPlaceholder")}
          value={description}
          onValueChange={setDescription}
        />
      </div>
      <div className="mt-auto pt-6 space-x-1 flex flex-row justify-end items-center">
        <Button color="orange" size="xs" variant="secondary" onClick={onCancel}>
          {t("common.actions.cancel")}
        </Button>
        <Button
          disabled={!isSubmitEnabled}
          variant="primary"
          color="orange"
          size="xs"
          type="submit"
        >
          {t("common.actions.update")}
        </Button>
      </div>
    </form>
  );
}
