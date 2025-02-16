import { ExclamationCircleIcon } from "@heroicons/react/24/outline";
import { Card, Callout } from "@tremor/react";
import dynamic from "next/dynamic";
import { Suspense, useEffect, useState } from "react";
import { EmptyBuilderState } from "./empty-builder-state";
import { Provider } from "@/app/(keep)/providers/providers";
import { useProviders } from "@/utils/hooks/useProviders";
import { useWorkflowStore } from "@/entities/workflows";
import { KeepLoader } from "@/shared/ui";
import clsx from "clsx";

const Builder = dynamic(() => import("./builder"), {
  ssr: false, // Prevents server-side rendering
});

interface Props {
  fileContents: string | null;
  workflow?: string;
  workflowId?: string;
  standalone?: boolean;
}

export function BuilderCard({
  fileContents,
  workflow,
  workflowId,
  standalone = false,
}: Props) {
  const [providers, setProviders] = useState<Provider[] | null>(null);
  const [installedProviders, setInstalledProviders] = useState<
    Provider[] | null
  >(null);
  const { setButtonsEnabled } = useWorkflowStore();

  const { data, error, isLoading } = useProviders();

  useEffect(() => {
    if (data && !providers && !installedProviders) {
      setProviders(data.providers);
      setInstalledProviders(data.installed_providers);
      setButtonsEnabled(true);
    }
  }, [data, providers, installedProviders, setButtonsEnabled]);

  const cardClassName = clsx(
    "mt-2 p-0 overflow-hidden",
    standalone
      ? "h-[calc(100vh-150px)]"
      : "h-full rounded-none border-t border-gray-200 shadow-none ring-0"
  );

  if (!providers || isLoading)
    return (
      <Card className={cardClassName}>
        <KeepLoader loadingText="Loading providers..." />
      </Card>
    );

  if (error) {
    return (
      <Card className={cardClassName}>
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
      <Card className={cardClassName}>
        <EmptyBuilderState />
      </Card>
    );
  }

  return (
    <Suspense
      fallback={<KeepLoader loadingText="Loading workflow builder..." />}
    >
      <Card className={cardClassName}>
        <Builder
          providers={providers}
          installedProviders={installedProviders}
          loadedAlertFile={fileContents}
          workflow={workflow}
          workflowId={workflowId}
        />
      </Card>
    </Suspense>
  );
}
