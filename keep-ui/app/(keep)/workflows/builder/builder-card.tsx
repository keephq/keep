import { ExclamationCircleIcon } from "@heroicons/react/24/outline";
import { Card, Callout } from "@tremor/react";
import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import Loader from "./loader";
import { Provider } from "../../providers/providers";
import { useProviders } from "utils/hooks/useProviders";
import clsx from "clsx";

const Builder = dynamic(() => import("./builder"), {
  ssr: false, // Prevents server-side rendering
});

interface Props {
  fileContents: string | null;
  fileName: string;
  enableButtons: () => void;
  enableGenerate: (state: boolean) => void;
  triggerGenerate: number;
  triggerSave: number;
  triggerRun: number;
  workflow?: string;
  workflowId?: string;
  isPreview?: boolean;
}

export function BuilderCard({
  fileContents,
  fileName,
  enableButtons,
  enableGenerate,
  triggerGenerate,
  triggerRun,
  triggerSave,
  workflow,
  workflowId,
  isPreview,
}: Props) {
  const [providers, setProviders] = useState<Provider[] | null>(null);
  const [installedProviders, setInstalledProviders] = useState<
    Provider[] | null
  >(null);

  const { data, error, isLoading } = useProviders();

  useEffect(() => {
    if (data && !providers && !installedProviders) {
      setProviders(data.providers);
      setInstalledProviders(data.installed_providers);
      enableButtons();
    }
  }, [data, providers, installedProviders, enableButtons]);

  if (!providers || isLoading)
    return (
      <Card className="mt-10 p-4 md:p-10 mx-auto">
        <Loader />
      </Card>
    );

  return (
    <Card
      className={clsx(
        "mt-2 p-0 mx-auto",
        error ? null : "h-[95%]",
        workflow ? "h-full" : "h-[95%]"
      )}
    >
      {error ? (
        <Callout
          className="mt-4"
          title="Error"
          icon={ExclamationCircleIcon}
          color="rose"
        >
          Failed to load providers
        </Callout>
      ) : fileContents == "" && !workflow ? (
        <Loader />
      ) : (
        <Builder
          providers={providers}
          installedProviders={installedProviders}
          loadedAlertFile={fileContents}
          fileName={fileName}
          enableGenerate={enableGenerate}
          triggerGenerate={triggerGenerate}
          triggerSave={triggerSave}
          triggerRun={triggerRun}
          workflow={workflow}
          workflowId={workflowId}
          isPreview={isPreview}
        />
      )}
    </Card>
  );
}
