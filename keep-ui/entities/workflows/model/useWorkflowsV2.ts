import useSWR, { mutate, SWRConfiguration } from "swr";
import { useApi } from "@/shared/lib/hooks/useApi";
import { PaginatedWorkflowsResults } from "@/shared/api/workflows";

export interface WorkflowsQuery {
  cel?: string;
  limit?: number;
  offset?: number;
  sortBy?: string;
  sortDir?: "asc" | "desc";
}

const requestUrl = "/workflows/query?is_v2=true";

export function useWorkflowsV2(
  workflowsQuery: WorkflowsQuery | null,
  swrConfig?: SWRConfiguration
) {
  const api = useApi();

  const queryToPost = workflowsQuery
    ? {
        ...(workflowsQuery.cel !== undefined && { cel: workflowsQuery.cel }),
        ...(workflowsQuery.limit !== undefined && {
          limit: workflowsQuery.limit,
        }),
        ...(workflowsQuery.offset !== undefined && {
          offset: workflowsQuery.offset,
        }),
        ...(workflowsQuery.sortBy !== undefined && {
          sort_by: workflowsQuery.sortBy,
        }),
        ...(workflowsQuery.sortDir !== undefined && {
          sort_dir: workflowsQuery.sortDir,
        }),
      }
    : {};

  const cacheKey =
    api.isReady() && workflowsQuery
      ? [
          requestUrl,
          queryToPost.cel,
          queryToPost.limit,
          queryToPost.offset,
          queryToPost.sort_by,
          queryToPost.sort_dir,
        ]
          .filter(Boolean)
          .join("::")
      : null;

  const { data, error, isLoading } = useSWR<PaginatedWorkflowsResults>(
    api.isReady() && workflowsQuery ? cacheKey : null,
    () => api.post(requestUrl, queryToPost),
    swrConfig
  );

  return {
    workflows: data?.results,
    totalCount: data?.count,
    isLoading: isLoading || !data,
    error,
  };
}

export function useRevalidateWorkflowsList() {
  return () => {
    mutate(
      (key) => typeof key === "string" && key.split("::")[0] === requestUrl
    );
  };
}
