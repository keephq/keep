import useSWR, { mutate } from "swr";
import { useApi } from "@/shared/lib/hooks/useApi";
import { Workflow } from "@/shared/api/workflows";
import { useEffect, useState } from "react";

export interface WorkflowsQuery {
  cel?: string;
  limit?: number;
  offset?: number;
  sortBy?: string;
  sortDir?: "asc" | "desc";
}

export function useWorkflowsV2(workflowsQuery: WorkflowsQuery | null) {
  const api = useApi();
  const queryToPost: { [key: string]: any } = {};

  if (workflowsQuery?.cel) {
    queryToPost.cel = workflowsQuery.cel;
  }

  if (workflowsQuery?.limit !== undefined) {
    queryToPost.limit = workflowsQuery.limit;
  }

  if (workflowsQuery?.offset !== undefined) {
    queryToPost.offset = workflowsQuery.offset;
  }

  if (workflowsQuery?.sortBy) {
    queryToPost.sort_by = workflowsQuery.sortBy;
  }

  if (workflowsQuery?.sortDir) {
    queryToPost.sort_dir = workflowsQuery.sortDir;
  }

  let requestUrl = "/workflows/query?is_v2=true";

  const [isLoading, setIsLoading] = useState(true);
  const {
    data,
    error,
    isLoading: isLoadingSwr,
  } = useSWR<any>(
    api.isReady() && workflowsQuery
      ? Object.entries(queryToPost)
          .map(([key, value]) => `${key}=${value}`)
          .join(";")
      : null,
    () => api.post(requestUrl, queryToPost)
  );
  useEffect(() => setIsLoading(isLoadingSwr), [isLoadingSwr]);

  const mutateWorkflows = () => {
    return mutate(requestUrl);
  };

  return {
    workflows: data?.results as Workflow[],
    totalCount: data?.count,
    isLoading,
    error,
    mutateWorkflows,
  };
}
