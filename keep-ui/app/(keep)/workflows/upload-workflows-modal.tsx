import { useI18n } from "@/i18n/hooks/useI18n";
import React from "react";
import { ChangeEvent, useRef, useState } from "react";
import { Button } from "@tremor/react";
import { ArrowRightIcon } from "@radix-ui/react-icons";
import { useRouter } from "next/navigation";
import Modal from "@/components/ui/Modal";
import { Input } from "@/shared/ui";
import { Textarea } from "@/components/ui";
import { useWorkflowActions } from "@/entities/workflows/model/useWorkflowActions";

const EXAMPLE_WORKFLOW_DEFINITIONS = {
  slack: `
      workflow:
        id: slack-demo
        description: Send a slack message when any alert is triggered or manually
        triggers:
          - type: alert
          - type: manual
        actions:
          - name: trigger-slack
            provider:
              type: slack
              config: " {{ providers.slack }} "
              with:
                message: "Workflow ran | reason: {{ event.trigger }}"
      `,
  sql: `
      workflow:
        id: bq-sql-query
        description: Run SQL on Bigquery and send the results to slack
        triggers:
          - type: manual
        steps:
          - name: get-sql-data
            provider:
              type: bigquery
              config: "{{ providers.bigquery-prod }}"
              with:
                query: "SELECT * FROM some_database LIMIT 1"
        actions:
          - name: trigger-slack
            provider:
              type: slack
              config: " {{ providers.slack-prod }} "
              with:
                message: "Results from the DB: ({{ steps.get-sql-data.results }})"
    `,
};

type ExampleWorkflowKey = keyof typeof EXAMPLE_WORKFLOW_DEFINITIONS;

interface UploadWorkflowsModalProps {
  onClose: () => void;
}

export const UploadWorkflowsModal: React.FC<UploadWorkflowsModalProps> = ({
  onClose,
}) => {
  const { t } = useI18n();
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [workflowDefinition, setWorkflowDefinition] = useState("");
  const { uploadWorkflowFiles } = useWorkflowActions();
  const router = useRouter();

  const onDrop = async (files: ChangeEvent<HTMLInputElement>) => {
    if (!files.target.files) {
      return;
    }

    const uploadedWorkflowsIds = await uploadWorkflowFiles(files.target.files);

    if (fileInputRef.current) {
      // Reset the file input to allow for multiple uploads
      fileInputRef.current.value = "";
    }

    onClose();
    if (uploadedWorkflowsIds.length === 1) {
      // If there is only one file, redirect to the workflow detail page
      router.push(`/workflows/${uploadedWorkflowsIds[0]}`);
    }
  };

  function handleWorkflowDefinitionString(
    workflowDefinition: string,
    name: string = "New workflow"
  ) {
    const blob = new Blob([workflowDefinition], {
      type: "application/x-yaml",
    });
    const file = new File([blob], `${name}.yml`, {
      type: "application/x-yaml",
    });
    const event = {
      target: {
        files: [file],
      },
    };
    onDrop(event as any);
  }

  function handleStaticExampleSelect(exampleKey: ExampleWorkflowKey) {
    switch (exampleKey) {
      case "slack":
        handleWorkflowDefinitionString(EXAMPLE_WORKFLOW_DEFINITIONS.slack);
        break;
      case "sql":
        handleWorkflowDefinitionString(EXAMPLE_WORKFLOW_DEFINITIONS.sql);
        break;
      default:
        throw new Error(`Invalid example workflow key: ${exampleKey}`);
    }
    onClose();
  }

  return (
    <Modal isOpen={true} onClose={onClose} title={t("workflows.uploadModal.title")}>
      <div className="bg-white rounded max-w-lg max-h-fit	 mx-auto z-20">
        <div className="space-y-2">
          <Input
            ref={fileInputRef}
            id="workflowFile"
            name="file"
            type="file"
            className="mt-2"
            accept=".yml, .yaml"
            multiple
            onChange={(e) => {
              onDrop(e);
              onClose(); // Add this line to close the modal
            }}
          />
          <p className="mt-2 text-xs text-gray-500 dark:text-gray-500">
            {t("workflows.uploadModal.supportedFormats")}
          </p>
        </div>
        <div className="mt-4">
          <h3>{t("workflows.uploadModal.orPasteYaml")}</h3>
          <Textarea
            id="workflowDefinition"
            onChange={(e) => {
              setWorkflowDefinition(e.target.value);
            }}
            name="workflowDefinition"
            className="mt-2"
          />
          <Button
            className="mt-2"
            color="orange"
            size="md"
            variant="primary"
            onClick={() => handleWorkflowDefinitionString(workflowDefinition)}
          >
            {t("workflows.uploadModal.load")}
          </Button>
        </div>
        <div className="mt-4 text-sm">
          <h3>{t("workflows.uploadModal.orTryExamples")}</h3>
          <Button
            className="mt-2"
            color="orange"
            size="md"
            variant="secondary"
            icon={ArrowRightIcon}
            onClick={() => handleStaticExampleSelect("slack")}
          >
            {t("workflows.uploadModal.slackExample")}
          </Button>

          <Button
            className="mt-2"
            color="orange"
            size="md"
            variant="secondary"
            icon={ArrowRightIcon}
            onClick={() => handleStaticExampleSelect("sql")}
          >
            {t("workflows.uploadModal.sqlExample")}
          </Button>

          <p className="mt-2">
            {t("workflows.uploadModal.moreExamplesAt")}{" "}
            <a
              href="https://github.com/keephq/keep/tree/main/examples/workflows"
              target="_blank"
            >
              {t("workflows.uploadModal.githubRepo")}
            </a>
          </p>
        </div>

        <div className="mt-4">
          <Button
            className="mt-2"
            color="orange"
            variant="secondary"
            onClick={() => onClose()}
          >
            {t("common.actions.cancel")}
          </Button>
        </div>
      </div>
    </Modal>
  );
};
