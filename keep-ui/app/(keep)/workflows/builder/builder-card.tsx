import { ExclamationCircleIcon } from "@heroicons/react/24/outline";
import { Card, Callout } from "@tremor/react";
import dynamic from "next/dynamic";
import { Suspense, useEffect, useState } from "react";
import { EmptyBuilderState } from "./empty-builder-state";
import { Provider } from "../../providers/providers";
import { useProviders } from "utils/hooks/useProviders";
import useStore from "./builder-store";
import Loading from "../../loading";

const Builder = dynamic(() => import("./builder"), {
  ssr: false, // Prevents server-side rendering
});

interface Props {
  fileContents: string | null;
  workflow?: string;
  workflowId?: string;
}

export function BuilderCard({ fileContents, workflow, workflowId }: Props) {
  const [providers, setProviders] = useState<Provider[] | null>(null);
  const [installedProviders, setInstalledProviders] = useState<
    Provider[] | null
  >(null);
  const { setButtonsEnabled } = useStore();

  const { data, error, isLoading } = useProviders();

  useEffect(() => {
    if (data && !providers && !installedProviders) {
      setProviders(data.providers);
      setInstalledProviders(data.installed_providers);
      setButtonsEnabled(true);
    }
  }, [data, providers, installedProviders, setButtonsEnabled]);

  if (!providers || isLoading)
    return (
      <Card className="mt-2 p-4 mx-auto">
        <Loading loadingText="Loading providers..." />
      </Card>
    );

  if (error) {
    return (
      <Card className="mt-2 p-4 mx-auto">
        <Callout
          className="mt-4"
          title="Error"
          icon={ExclamationCircleIcon}
          color="rose"
        >
          Failed to load providers
        </Callout>
      </Card>
    );
  }

  if (fileContents == "" && !workflow) {
    return (
      <Card className="mt-2 p-4 mx-auto h-[95%]">
        <EmptyBuilderState />
      </Card>
    );
  }

  return (
    <Suspense fallback={<Loading loadingText="Loading workflow builder..." />}>
      <Builder
        providers={providers}
        installedProviders={installedProviders}
        loadedAlertFile={fileContents}
        workflow={workflow}
        workflowId={workflowId}
      />
    </Suspense>
  );
}
