"use client";

import { ChangeEvent, useRef, useState } from "react";
import { Subtitle, Button } from "@tremor/react";
import {
  ArrowUpOnSquareStackIcon,
  PlusCircleIcon,
} from "@heroicons/react/24/outline";
import { KeepLoader, PageTitle } from "@/shared/ui";
import WorkflowsEmptyState from "./noworkflows";
import WorkflowTile from "./workflow-tile";
import { ArrowRightIcon } from "@radix-ui/react-icons";
import { useRouter } from "next/navigation";
import Modal from "@/components/ui/Modal";
import { WorkflowTemplates } from "./mockworkflows";
import { useApi } from "@/shared/lib/hooks/useApi";
import { Input, ErrorComponent } from "@/shared/ui";
import { Textarea } from "@/components/ui";
import { useWorkflowsV2 } from "utils/hooks/useWorkflowsV2";
import { useWorkflowActions } from "@/entities/workflows/model/useWorkflowActions";
import { PageSubtitle } from "@/shared/ui/PageSubtitle";
import { PlusIcon } from "@heroicons/react/20/solid";

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

export default function WorkflowsPage() {
  const api = useApi();
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [workflowDefinition, setWorkflowDefinition] = useState("");
  const [isModalOpen, setIsModalOpen] = useState(false);

  // Only fetch data when the user is authenticated
  /**
    Redesign the workflow Card
      The workflow card needs execution records (currently limited to 15) for the graph. To achieve this, the following changes
      were made in the backend:
      1. Query Search Parameter: A new query search parameter called is_v2 has been added, which accepts a boolean
        (default is false).
      2. Grouped Workflow Executions: When a request is made with /workflows?is_v2=true, workflow executions are grouped
         by workflow.id.
      3. Response Updates: The response includes the following new keys and their respective information:
          -> last_executions: Used for the workflow execution graph.
          ->last_execution_started: Used for showing the start time of execution in real-time.
  **/
  const { workflows, error, isLoading } = useWorkflowsV2();
  const { uploadWorkflowFiles } = useWorkflowActions();

  if (error) {
    return <ErrorComponent error={error} reset={() => {}} />;
  }

  if (isLoading || !workflows) {
    return <KeepLoader />;
  }

  const onDrop = async (files: ChangeEvent<HTMLInputElement>) => {
    if (!files.target.files) {
      return;
    }

    const uploadedWorkflowsIds = await uploadWorkflowFiles(files.target.files);

    if (fileInputRef.current) {
      // Reset the file input to allow for multiple uploads
      fileInputRef.current.value = "";
    }

    setIsModalOpen(false);
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
    setIsModalOpen(false);
  }

  return (
    <>
      <main className="flex flex-col gap-8">
        <div className="flex flex-col gap-6">
          <div className="flex justify-between items-center">
            <div>
              <PageTitle>Workflows</PageTitle>
              <PageSubtitle>
                Automate your alert management with workflows
              </PageSubtitle>
            </div>
            <div className="flex gap-2">
              <Button
                color="orange"
                size="md"
                variant="secondary"
                onClick={() => {
                  setIsModalOpen(true);
                }}
                icon={ArrowUpOnSquareStackIcon}
                id="uploadWorkflowButton"
              >
                Upload Workflows
              </Button>
              <Button
                color="orange"
                size="md"
                variant="primary"
                onClick={() => router.push("/workflows/builder")}
                icon={PlusIcon}
              >
                Create Workflow
              </Button>
            </div>
          </div>
          {workflows.length === 0 ? (
            <WorkflowsEmptyState isNewUI={true} />
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 w-full gap-4">
              {workflows.map((workflow) => (
                <WorkflowTile key={workflow.id} workflow={workflow} />
              ))}
            </div>
          )}
        </div>
        <div className="flex flex-col gap-4">
          <WorkflowTemplates />
        </div>
      </main>
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title="Upload Workflow files"
      >
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
                setIsModalOpen(false); // Add this line to close the modal
              }}
            />
            <p className="mt-2 text-xs text-gray-500 dark:text-gray-500">
              Only .yml and .yaml files are supported.
            </p>
          </div>
          <div className="mt-4">
            <h3>Or paste the YAML definition:</h3>
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
              Load
            </Button>
          </div>
          <div className="mt-4 text-sm">
            <h3>Or just try some from Keep examples:</h3>
            <Button
              className="mt-2"
              color="orange"
              size="md"
              variant="secondary"
              icon={ArrowRightIcon}
              onClick={() => handleStaticExampleSelect("slack")}
            >
              Send a Slack message for every alert or manually
            </Button>

            <Button
              className="mt-2"
              color="orange"
              size="md"
              variant="secondary"
              icon={ArrowRightIcon}
              onClick={() => handleStaticExampleSelect("sql")}
            >
              Run SQL query and send the results as a Slack message
            </Button>

            <p className="mt-2">
              More examples at{" "}
              <a
                href="https://github.com/keephq/keep/tree/main/examples/workflows"
                target="_blank"
              >
                Keep GitHub repo
              </a>
            </p>
          </div>

          <div className="mt-4">
            <Button
              className="mt-2"
              color="orange"
              variant="secondary"
              onClick={() => setIsModalOpen(false)}
            >
              Cancel
            </Button>
          </div>
        </div>
      </Modal>
    </>
  );
}
