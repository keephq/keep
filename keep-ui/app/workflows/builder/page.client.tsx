"use client";

import { Title, Button, Subtitle, Badge } from "@tremor/react";
import { useEffect, useState } from "react";
import {
  PlusIcon,
  ArrowDownOnSquareIcon,
  BoltIcon,
  ArrowUpOnSquareIcon,
  PlayIcon,
} from "@heroicons/react/20/solid";
import { useSession } from "next-auth/react";
import { BuilderCard } from "./builder-card";
import Loading from "../../loading";

export default function PageClient({
  workflow,
  workflowId,
  isPreview,
}: {
  workflow?: string;
  workflowId?: string;
  isPreview?: boolean;
}) {
  const [buttonsEnabled, setButtonsEnabled] = useState(false);
  const [generateEnabled, setGenerateEnabled] = useState(false);
  const [triggerGenerate, setTriggerGenerate] = useState(0);
  const [triggerSave, setTriggerSave] = useState(0);
  const [triggerRun, setTriggerRun] = useState(0);
  const [fileContents, setFileContents] = useState<string | null>("");
  const [fileName, setFileName] = useState("");
  const { data: session, status, update } = useSession();

  useEffect(() => {
    setFileContents(null);
    setFileName("");
  });

  function loadAlert() {
    document.getElementById("alertFile")?.click();
  }

  function newAlert() {
    const confirmed = confirm("Are you sure you want to create a new alert?");
    if (confirmed) window.location.reload();
  }

  const enableButtons = () => setButtonsEnabled(true);
  const enableGenerate = (state: boolean) => setGenerateEnabled(state);

  function handleFileChange(event: any) {
    const file = event.target.files[0];
    const fName = event.target.files[0].name;
    const reader = new FileReader();
    reader.onload = (event) => {
      setFileName(fName);
      const contents = event.target!.result as string;
      setFileContents(contents);
    };
    reader.readAsText(file);
  }
  if (status === "loading" || status === "unauthenticated")
    return (
      <div>
        <Loading />
      </div>
    );

  const incrementState = (s: number) => s + 1;

  return (
    <main className="p-4 md:p-5 mx-auto max-w-full h-[98%]">
      <div className="flex justify-between">
        <div className="flex flex-col">
          <Title>
            Builder
            <Badge
              color="orange"
              size="xs"
              tooltip="Slack us if something isn't working properly :)"
            >
              Beta
            </Badge>
          </Title>
          <Subtitle>Workflow building kit</Subtitle>
        </div>
        <div className="flex gap-2">
          {!workflow && (
            <>
              <Button
                color="orange"
                size="md"
                onClick={newAlert}
                icon={PlusIcon}
                className="min-w-28"
                variant="secondary"
                disabled={!buttonsEnabled}
              >
                New
              </Button>
              <Button
                color="orange"
                size="md"
                onClick={loadAlert}
                className="min-w-28"
                variant="secondary"
                icon={ArrowDownOnSquareIcon}
                disabled={!buttonsEnabled}
              >
                Load
              </Button>
              <input
                type="file"
                id="alertFile"
                style={{ display: "none" }}
                onChange={handleFileChange}
              />
            </>
          )}
          <Button
            color="orange"
            size="md"
            className="min-w-28"
            icon={PlayIcon}
            disabled={!generateEnabled}
            onClick={() => setTriggerRun(incrementState)}
          >
            Run
          </Button>
          <Button
            color="orange"
            size="md"
            className="min-w-28"
            icon={ArrowUpOnSquareIcon}
            disabled={!generateEnabled}
            onClick={() => setTriggerSave(incrementState)}
          >
            Deploy
          </Button>
          {!workflow && (
            <Button
              disabled={!generateEnabled}
              color="orange"
              size="md"
              className="min-w-28"
              icon={BoltIcon}
              onClick={() => setTriggerGenerate(incrementState)}
            >
              Generate
            </Button>
          )}
        </div>
      </div>
      <BuilderCard
        accessToken={session?.accessToken!}
        fileContents={fileContents}
        fileName={fileName}
        enableButtons={enableButtons}
        enableGenerate={enableGenerate}
        triggerGenerate={triggerGenerate}
        triggerRun={triggerRun}
        triggerSave={triggerSave}
        workflow={workflow}
        workflowId={workflowId}
        isPreview={isPreview}
      />
    </main>
  );
}
