import useSWR, { mutate, SWRConfiguration } from "swr";
import { useApi } from "@/shared/lib/hooks/useApi";
import { Workflow } from "@/shared/api/workflows";

export interface WorkflowsQuery {
  cel?: string;
  limit?: number;
  offset?: number;
  sortBy?: string;
  sortDir?: "asc" | "desc";
}

export function useWorkflowsV2(
  workflowsQuery: WorkflowsQuery | null,
  swrConfig?: SWRConfiguration
) {
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

  const { data, error, isLoading } = useSWR<any>(
    api.isReady() && workflowsQuery
      ? requestUrl + JSON.stringify(queryToPost)
      : null,
    () => api.post(requestUrl, queryToPost),
    swrConfig
  );

  const mutateWorkflows = () => {
    return mutate(
      (key) => typeof key === "string" && key.startsWith(requestUrl)
    );
  };

  return {
    workflows: data?.results as Workflow[],
    totalCount: data?.count,
    isLoading: isLoading || !data,
    error,
    mutateWorkflows,
  };
}
