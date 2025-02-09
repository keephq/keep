import { ExclamationCircleIcon } from "@heroicons/react/24/outline";
import { Card, Callout } from "@tremor/react";
import dynamic from "next/dynamic";
import { useEffect } from "react";
import { EmptyBuilderState } from "./empty-builder-state";
import { useProviders } from "utils/hooks/useProviders";
import Loading from "../../loading";
import { useWorkflowStore } from "./workflow-store";
import { useSearchParams } from "next/navigation";

const Builder = dynamic(() => import("./builder").then((mod) => mod.Builder), {
  ssr: false, // Prevents server-side rendering
});

interface Props {
  fileContents: string | null;
  fileName: string;
  workflow?: string;
  workflowId?: string;
}

export function BuilderCard({
  fileContents,
  fileName,
  workflow,
  workflowId,
}: Props) {
  console.log("workflow=", workflow);
  console.log("workflowId=", workflowId);
  console.log("fileContents=", fileContents);
  console.log("fileName=", fileName);

  const initialize = useWorkflowStore((s) => s.initialize);
  const initializeEmpty = useWorkflowStore((s) => s.initializeEmpty);
  const initializedWorkflowId = useWorkflowStore((s) => s.v2Properties.id);
  const searchParams = useSearchParams();
  const isInitializing = useWorkflowStore((s) => s.isLoading);
  const { data, error, isLoading } = useProviders();

  const providers = data?.providers ?? [];
  const installedProviders = data?.installed_providers ?? [];

  // useEffect(() => {
  //   if (initializedWorkflowId || isInitializing || !providers) {
  //     return;
  //   }

  //   if (fileContents) {
  //     initialize(fileContents, providers);
  //   } else {
  //     const alertName = searchParams?.get("alertName");
  //     const alertSource = searchParams?.get("alertSource");

  //     initializeEmpty({
  //       alertName: alertName ?? undefined,
  //       alertSource: alertSource ?? undefined,
  //     });
  //   }
  // }, []);

  if (!providers || isLoading)
    return (
      <Card className="mt-2 p-4 mx-auto">
        <Loading />
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
    <Builder
      providers={providers}
      installedProviders={installedProviders}
      loadedAlertFile={fileContents}
      workflow={workflow}
      workflowId={workflowId}
    />
  );
}
