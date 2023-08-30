"use client";

import { useRef, useState } from "react";
import useSWR from "swr";
import { Callout, Col, Grid, Subtitle } from "@tremor/react";
import {
  ArrowDownOnSquareIcon,
  ExclamationCircleIcon,
} from "@heroicons/react/24/outline";
import { useSession } from "../../utils/customAuth";
import { fetcher } from "../../utils/fetcher";
import { Workflow } from "./models";
import { getApiURL } from "../../utils/apiUrl";
import Loading from "../loading";
import React from "react";
import WorkflowsEmptyState from "./noworfklows";
import WorkflowTile from "./workflow-tile";
import { Button, Card, Title } from "@tremor/react";

function copyToClipboard(text: string) {
  const textarea = document.createElement("textarea");
  textarea.value = text;
  document.body.appendChild(textarea);
  textarea.select();
  document.execCommand("copy");
  document.body.removeChild(textarea);
}

export default function WorkflowsPage() {
  const apiUrl = getApiURL();
  const { data: session, status, update } = useSession();
  const [copied, setCopied] = useState(false);
  const [fileContents, setFileContents] = useState<string | null>("");
  const [fileError, setFileError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Only fetch data when the user is authenticated
  const { data, error, isLoading } = useSWR<Workflow[]>(
    status === "authenticated" ? `${apiUrl}/workflows` : null,
    (url) => fetcher(url, session?.accessToken!)
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
    const formData = new FormData();
    const file = files.target.files[0];
    formData.append("file", file);

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
        window.location.reload();
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

  function handleFileChange(event: any) {
    const file = event.target.files[0];
    const reader = new FileReader();
    reader.onload = (event) => {
      const contents = event.target!.result as string;
      setFileContents(contents);
      // Do something with the file contents
    };
    reader.readAsText(file);
  }

  function loadAlert() {
    document.getElementById("workflowFile")?.click();
  }

  return (
    <main className="p-4 md:p-10 mx-auto max-w-full">
      <div className="flex justify-between items-center">
        <div>
          <Title>Workflows</Title>
          <Subtitle>Automate your alert management with workflows.</Subtitle>
        </div>
        <Button
          color="orange"
          size="md"
          onClick={loadAlert}
          icon={ArrowDownOnSquareIcon}
        >
          Load a Workflow
        </Button>
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
      <input
        type="file"
        id="workflowFile"
        style={{ display: "none" }}
        onChange={onDrop}
      />
    </main>
  );
}
