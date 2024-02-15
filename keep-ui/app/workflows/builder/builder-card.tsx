import { ExclamationCircleIcon } from "@heroicons/react/24/outline";
import { Card, Callout } from "@tremor/react";
import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { getApiURL } from "../../../utils/apiUrl";
import Loader from "./loader";
import { Provider } from "../../providers/providers";
import { KeepApiError } from "../../error";
import { useProviders } from "utils/hooks/useProviders";

const Builder = dynamic(() => import("./builder"), {
  ssr: false, // Prevents server-side rendering
});

interface Props {
  accessToken: string;
  fileContents: string | null;
  fileName: string;
  enableButtons: () => void;
  enableGenerate: (state: boolean) => void;
  triggerGenerate: number;
  triggerSave: number;
  workflow?: string;
  workflowId?: string;
}

export function BuilderCard({
  accessToken,
  fileContents,
  fileName,
  enableButtons,
  enableGenerate,
  triggerGenerate,
  triggerSave,
  workflow,
  workflowId,
}: Props) {
  const [providers, setProviders] = useState<Provider[] | null>(null);
  const [installedProviders, setInstalledProviders] = useState<
    Provider[] | null
  >(null);
  const apiUrl = getApiURL();

  const { data, error, isLoading } = useProviders();

  if (error) {
    throw new KeepApiError(
      "The builder has failed to load providers",
      `${apiUrl}/providers`
    );
  }

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
    <Card className={`mt-10 p-4 md:p-10 mx-auto ${error ? null : "h-5/6"}`}>
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
          workflow={workflow}
          accessToken={accessToken}
          workflowId={workflowId}
        />
      )}
    </Card>
  );
}
