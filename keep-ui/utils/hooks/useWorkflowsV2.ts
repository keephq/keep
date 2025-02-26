import useSWR, { mutate } from "swr";
import { useApi } from "@/shared/lib/hooks/useApi";
import { Workflow } from "@/shared/api/workflows";
import { useEffect } from "react";

export interface WorkflowsQuery {
  cel?: string;
  limit?: number;
  offset?: number;
  sortBy?: string;
  sortDir?: "asc" | "desc";
}

export function useWorkflowsV2(
  workflowsQuery: WorkflowsQuery | null,
  foo?: boolean
) {
  const api = useApi();
  const urlSearchParams = new URLSearchParams();

  urlSearchParams.append("is_v2", "true");

  if (workflowsQuery?.cel) {
    urlSearchParams.append("cel", workflowsQuery.cel);
  }

  if (workflowsQuery?.limit !== undefined) {
    urlSearchParams.append("limit", workflowsQuery.limit.toString());
  }

  if (workflowsQuery?.offset !== undefined) {
    urlSearchParams.append("offset", workflowsQuery.offset.toString());
  }

  if (workflowsQuery?.sortBy) {
    urlSearchParams.append("sort_by", workflowsQuery.sortBy);
  }

  if (workflowsQuery?.sortDir) {
    urlSearchParams.append("sort_dir", workflowsQuery.sortDir);
  }

  let requestUrl = "/workflows";

  if (urlSearchParams.toString()) {
    requestUrl += `?${urlSearchParams.toString()}`;
  }

  useEffect(() => {
    if (foo) {
      return;
    }
    console.log({
      text: "Ihor",
      workflowsQuery,
    });
  }, [workflowsQuery, foo]);

  const { data, error, isLoading } = useSWR<any>(
    api.isReady() && workflowsQuery ? requestUrl : null,
    (url: string) => api.get(url)
  );

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
