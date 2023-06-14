"use client";

import { Title, Text, Button } from "@tremor/react";
import { useState } from "react";
import {
  PlusIcon,
  ArrowDownOnSquareIcon,
  BoltIcon,
} from "@heroicons/react/20/solid";
import { useSession } from "../../utils/customAuth";
import { BuilderCard } from "./builder-card";
import Loading from "../loading";

export default function PageClient() {
  const [buttonsEnabled, setButtonsEnabled] = useState(false);
  const [generateEnabled, setGenerateEnabled] = useState(false);
  const [triggerGenerate, setTriggerGenerate] = useState(0);
  const [fileContents, setFileContents] = useState<string | null>("");
  const [fileName, setFileName] = useState("");
  const { data: session, status, update } = useSession();
  function loadAlert() {
    document.getElementById("alertFile")?.click();
  }

  function newAlert() {
    setFileContents(null);
    setFileName("");
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
  if (status === "loading") return <div><Loading/></div>;
  if (status === "unauthenticated") return <div>Unauthenticated...</div>;

  return (
    <main className="p-4 md:p-10 mx-auto max-w-7xl h-full">
      <div className="flex justify-between">
        <div className="flex flex-col">
          <Title>Builder</Title>
          <Text>Alert building kit</Text>
        </div>
        <div>
          <Button
            color="orange"
            size="md"
            className="mr-2"
            onClick={newAlert}
            icon={PlusIcon}
            variant="secondary"
            disabled={!buttonsEnabled}
          >
            New
          </Button>
          <Button
            color="orange"
            size="md"
            className="mr-2"
            onClick={loadAlert}
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
          <Button
            disabled={!generateEnabled}
            color="orange"
            size="md"
            icon={BoltIcon}
            onClick={() => setTriggerGenerate(triggerGenerate + 1)}
          >
            Generate
          </Button>
        </div>
      </div>
      <BuilderCard
        accessToken={session?.accessToken!}
        fileContents={fileContents}
        fileName={fileName}
        enableButtons={enableButtons}
        enableGenerate={enableGenerate}
        triggerGenerate={triggerGenerate}
      />
    </main>
  );
}
