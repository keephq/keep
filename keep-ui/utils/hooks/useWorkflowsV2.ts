import useSWR, { mutate } from "swr";
import { useApi } from "@/shared/lib/hooks/useApi";
import { Workflow } from "@/shared/api/workflows";

export function useWorkflowsV2(params: {
  cel?: string;
  limit?: number;
  offset?: number;
  sortBy?: string;
  sortDir?: "asc" | "desc";
}) {
  const api = useApi();
  const urlSearchParams = new URLSearchParams();

  urlSearchParams.append("is_v2", "true");

  if (params.cel) {
    urlSearchParams.append("cel", params.cel);
  }

  if (params.limit) {
    urlSearchParams.append("limit", params.limit.toString());
  }

  if (params.offset) {
    urlSearchParams.append("offset", params.offset.toString());
  }

  if (params.sortBy) {
    urlSearchParams.append("sort_by", params.sortBy);
  }

  if (params.sortDir) {
    urlSearchParams.append("sort_dir", params.sortDir);
  }

  let requestUrl = "/workflows";

  if (urlSearchParams.toString()) {
    requestUrl += `?${urlSearchParams.toString()}`;
  }

  const { data, error, isLoading } = useSWR<any>(
    api.isReady() ? requestUrl : null,
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
