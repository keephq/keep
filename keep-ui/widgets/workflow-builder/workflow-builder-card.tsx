import { ExclamationCircleIcon } from "@heroicons/react/24/outline";
import { Card, Callout } from "@tremor/react";
import dynamic from "next/dynamic";
import { Suspense } from "react";
import { EmptyBuilderState } from "./empty-builder-state";
import { useProviders } from "@/utils/hooks/useProviders";
import { KeepLoader } from "@/shared/ui";
import clsx from "clsx";

const Builder = dynamic(
  () => import("./workflow-builder").then((mod) => mod.WorkflowBuilder),
  {
    ssr: false, // Prevents server-side rendering
  }
);

interface Props {
  loadedYamlFileContents: string | null;
  workflowRaw?: string;
  workflowId?: string;
  standalone?: boolean;
}

export function WorkflowBuilderCard({
  loadedYamlFileContents,
  workflowRaw,
  workflowId,
  standalone = false,
}: Props) {
  const {
    data: { providers, installed_providers: installedProviders } = {},
    error,
    isLoading,
  } = useProviders();

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

  if (loadedYamlFileContents == "" && !workflowRaw) {
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
          loadedYamlFileContents={loadedYamlFileContents}
          workflowRaw={workflowRaw}
          workflowId={workflowId}
        />
      </Card>
    </Suspense>
  );
}
