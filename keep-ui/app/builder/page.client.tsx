"use client";

import { Card, Title, Text, Button, Callout } from "@tremor/react";
import { ExclamationCircleIcon } from "@heroicons/react/20/solid";
import dynamic from "next/dynamic";
import { useState } from "react";
import Loader from "./loader";
import useSWR from "swr";
import {
  PlusIcon,
  ArrowDownOnSquareIcon,
  BoltIcon,
} from "@heroicons/react/20/solid";
import { useSession } from "../../utils/customAuth";
import { getApiURL } from "../../utils/apiUrl";
import { Provider } from "../providers/providers";

const Builder = dynamic(() => import("./builder"), {
  ssr: false, // Prevents server-side rendering
});

const fetcher = (url: string, accessToken: string) =>
  fetch(url, {
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  });

interface Props {
  accessToken: string;
  fileContents: string | null;
  fileName: string;
  enableButtons: () => void;
  enableGenerate: (state: boolean) => void;
  triggerGenerate: number;
}

function Main({
  accessToken,
  fileContents,
  fileName,
  enableButtons,
  enableGenerate,
  triggerGenerate
}: Props) {
  const [providers, setProviders] = useState<{
    [providerType: string]: Provider;
  } | null>(null);
  const apiUrl = getApiURL();

  const { data, error, isLoading } = useSWR(`${apiUrl}/providers`, (url) =>
    fetcher(url, accessToken)
  );

  if (data?.ok && !providers) {
    if (!data.bodyUsed) {
      data.json().then((providers) => {
        setProviders(providers);
        enableButtons();
      });
    }
  }

  return (
    <Card
      className={`p-4 md:p-10 mx-auto max-w-7xl mt-6 ${
        error || (data && !data.ok) ? null : "h-5/6"
      }`}
    >
      {error || (data && !data.ok) ? (
        <Callout
          className="mt-4"
          title="Error"
          icon={ExclamationCircleIcon}
          color="rose"
        >
          Failed to load providers
        </Callout>
      ) : fileContents == "" || isLoading || !providers ? (
        <Loader />
      ) : (
        <Builder
          providers={providers}
          loadedAlertFile={fileContents}
          fileName={fileName}
          enableGenerate={enableGenerate}
          triggerGenerate={triggerGenerate}
        />
      )}
    </Card>
  );
}

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
  if (status === "loading") return <div>Loading...</div>;
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
      <Main
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
