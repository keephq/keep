import useSWR, { SWRConfiguration } from "swr";
import { useApi } from "@/shared/lib/hooks/useApi";
import { PaginatedWorkflowsResults } from "@/shared/api/workflows";
import { workflowKeys } from "./workflowKeys";

export const DEFAULT_WORKFLOWS_PAGINATION = {
  offset: 0,
  limit: 12,
};

export const DEFAULT_WORKFLOWS_QUERY = {
  cel: "",
  ...DEFAULT_WORKFLOWS_PAGINATION,
  sortBy: "created_at",
  sortDir: "desc" as const,
};

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
    api.isReady() && workflowsQuery ? workflowKeys.list(queryToPost) : null;

  const { data, error, isLoading } = useSWR<PaginatedWorkflowsResults>(
    cacheKey,
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
