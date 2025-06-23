"use client";

import { ErrorComponent, KeepLoader } from "@/shared/ui";
import { useWorkflowsV2 } from "@/entities/workflows/model/useWorkflowsV2";
import { InitialFacetsData } from "@/features/filter/api";
import { ExistingWorkflowsState } from "./existing-workflows-state";
import { NoWorkflowsState } from "./no-workflows-state";

export function WorkflowsPage({
  initialFacetsData,
}: {
  initialFacetsData?: InitialFacetsData;
}) {
  const { totalCount, error, isLoading } = useWorkflowsV2(
    { cel: "", limit: 0, offset: 0 },
    { keepPreviousData: true }
  );

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center h-full">
        <KeepLoader />
      </div>
    );
  }

  if (error) {
    return <ErrorComponent error={error} reset={() => {}} />;
  }

  if ((totalCount as number) > 0) {
    return <ExistingWorkflowsState initialFacetsData={initialFacetsData} />;
  }

  return <NoWorkflowsState></NoWorkflowsState>;
}
