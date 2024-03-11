"use client";

import { useRef, useState } from "react";
import useSWR from "swr";
import { Callout, Subtitle } from "@tremor/react";
import {
  ArrowUpOnSquareStackIcon,
  ExclamationCircleIcon,
  PlusCircleIcon,
} from "@heroicons/react/24/outline";
import { useSession } from "next-auth/react";
import { fetcher } from "../../utils/fetcher";
import { Workflow } from "./models";
import { getApiURL } from "../../utils/apiUrl";
import Loading from "../loading";
import React from "react";
import WorkflowsEmptyState from "./noworfklows";
import WorkflowTile from "./workflow-tile";
import { Button, Card, Title } from "@tremor/react";
import { ArrowRightIcon } from "@radix-ui/react-icons";
import { useRouter } from "next/navigation";
import Modal from "@/components/ui/Modal";

export default function WorkflowsPage() {
  const apiUrl = getApiURL();
  const router = useRouter();
  const { data: session, status, update } = useSession();
  const [fileError, setFileError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  // Only fetch data when the user is authenticated
  const { data, error, isLoading } = useSWR<Workflow[]>(
    status === "authenticated" ? `${apiUrl}/workflows` : null,
    (url: string) => fetcher(url, session?.accessToken!)
  );

  if (isLoading || !data) return <Loading />;

  if (error) {
    return (
      <Callout
        className="mt-4"
        title="Error"
        icon={ExclamationCircleIcon}
        color="rose"
      >
        Failed to load workflows
      </Callout>
    );
  }

  const onDrop = async (files: any) => {
    const fileUpload = async (formData: FormData, reload: boolean) => {
      try {
        const response = await fetch(`${apiUrl}/workflows`, {
          method: "POST",
          headers: {
            Authorization: `Bearer ${session?.accessToken}`,
          },
          body: formData,
        });
  
        if (response.ok) {
          setFileError(null);
          if (fileInputRef.current) {
            fileInputRef.current.value = "";
          }
          if (reload) {
            window.location.reload();
          }
        } else {
          const errorMessage = await response.text();
          setFileError(errorMessage);
          if (fileInputRef.current) {
            fileInputRef.current.value = "";
          }
        }
      } catch (error) {
        setFileError("An error occurred during file upload");
        if (fileInputRef.current) {
          fileInputRef.current.value = "";
        }
      }
    };

    const formData = new FormData();
    var reload = false;

    for (let i = 0; i < files.target.files.length; i++) {
      const file = files.target.files[i];
      formData.set("file", file);
      if (files.target.files.length === i + 1) {
        reload = true;
      }
      await fileUpload(formData, reload);
    };
  }

  function handleStaticExampleSelect(example: string) {
    // todo: something less static
    let hardCodedYaml = "";
    if (example === "slack") {
      hardCodedYaml = `
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
        `;
    } else {
      hardCodedYaml = `
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
              `;
    }
    const blob = new Blob([hardCodedYaml], { type: "application/x-yaml" });
    const file = new File([blob], `${example}.yml`, {
      type: "application/x-yaml",
    });

    const event = {
      target: {
        files: [file],
      },
    };
    onDrop(event as any);
    setIsModalOpen(false);
  }

  return (
    <main className="p-4 md:p-10 mx-auto max-w-full">
      <div className="flex justify-between items-center">
        <div>
          <Title>Workflows</Title>
          <Subtitle>Automate your alert management with workflows.</Subtitle>
        </div>
        <div>
          <Button
            className="mr-2.5"
            color="orange"
            size="md"
            variant="secondary"
            onClick={() => router.push("/workflows/builder")}
            icon={PlusCircleIcon}
          >
            Create a workflow
          </Button>
          <Button
            color="orange"
            size="md"
            onClick={() => {
              setIsModalOpen(true);
            }}
            icon={ArrowUpOnSquareStackIcon}
          >
            Upload Workflows
          </Button>
        </div>
        <Modal
          isOpen={isModalOpen}
          onClose={() => setIsModalOpen(false)}
          title="Upload Workflow files"
        >
          <div className="bg-white p-4 rounded max-w-lg max-h-fit	 mx-auto z-20">
            <input
              type="file"
              id="workflowFile"
              accept=".yml, .yaml" // accept only yamls
              multiple
              onChange={(e) => {
                onDrop(e);
                setIsModalOpen(false); // Add this line to close the modal
              }}
            />

            <div className="mt-4">
              <h3>Or just try some from Keep examples:</h3>

              <Button
                className="mt-2"
                color="orange"
                size="md"
                icon={ArrowRightIcon}
                onClick={() => handleStaticExampleSelect("slack")}
              >
                Send a Slack message for every alert or manually
              </Button>

              <Button
                className="mt-2"
                color="orange"
                size="md"
                icon={ArrowRightIcon}
                onClick={() => handleStaticExampleSelect("sql")}
              >
                Run SQL query and send the results as a Slack message
              </Button>

              <p className="mt-4">
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
              <button onClick={() => setIsModalOpen(false)}>Cancel</button>
            </div>
          </div>
        </Modal>
      </div>
      <Card className="mt-10 p-4 md:p-10 mx-auto">
        <div>
          <div>
            {data.length === 0 ? (
              <WorkflowsEmptyState />
            ) : (
              <div className="flex flex-wrap gap-2">
                {data.map((workflow) => (
                  <WorkflowTile key={workflow.id} workflow={workflow} />
                ))}
              </div>
            )}
          </div>
        </div>
      </Card>
    </main>
  );
}
