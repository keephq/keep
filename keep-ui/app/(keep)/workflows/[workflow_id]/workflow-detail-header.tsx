"use client";

import { useApi } from "@/shared/lib/hooks/useApi";
import { Workflow } from "../models";

import useSWR from "swr";
import Skeleton from "react-loading-skeleton";
import { Text } from "@tremor/react";

export default function WorkflowDetailHeader({
  workflow_id,
}: {
  workflow_id: string;
}) {
  const api = useApi();
  const {
    data: workflow,
    isLoading,
    error,
  } = useSWR<Partial<Workflow>>(
    api.isReady() ? `/workflows/${workflow_id}` : null,
    (url: string) => api.get(url)
  );

  if (error) {
    return <div>Error loading workflow</div>;
  }

  if (isLoading || !workflow) {
    return (
      <div>
        <h1 className="text-2xl line-clamp-2 font-extrabold">
          <Skeleton className="w-1/2 h-4" />
        </h1>
        <Skeleton className="w-3/4 h-4" />
        <Skeleton className="w-1/2 h-4" />
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-2xl line-clamp-2 font-extrabold">{workflow.name}</h1>
      {workflow.description && (
        <Text className="line-clamp-5">
          <span>{workflow.description}</span>
        </Text>
      )}
    </div>
  );
}
