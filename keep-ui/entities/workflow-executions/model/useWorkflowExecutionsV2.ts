import { PaginatedWorkflowExecutionDto } from "@/shared/api/workflow-executions";
import { useApi } from "@/shared/lib/hooks/useApi";
import { useSearchParams } from "next/navigation";
import useSWR from "swr";
import { workflowExecutionsKeys } from "./workflowExecutionsKeys";

export const useWorkflowExecutionsV2 = (
  workflowId: string,
  limit: number = 25,
  offset: number = 0
) => {
  const api = useApi();
  const searchParams = useSearchParams();
  limit = searchParams?.get("limit")
    ? Number(searchParams?.get("limit"))
    : limit;
  offset = searchParams?.get("offset")
    ? Number(searchParams?.get("offset"))
    : offset;
  limit = limit > 100 ? 50 : limit;
  limit = limit <= 0 ? 25 : limit;
  offset = offset < 0 ? 0 : offset;

  // Create new URLSearchParams without 'tab' param
  const filteredParams = new URLSearchParams();
  searchParams?.forEach((value, key) => {
    if (key !== "tab") {
      filteredParams.append(key, value);
    }
  });

  const cacheKey =
    api.isReady() && workflowId
      ? workflowExecutionsKeys.list(workflowId, {
          limit,
          offset,
          searchParamsString: filteredParams.toString(),
        })
      : null;

  const url = `/workflows/${workflowId}/runs?v2=true&limit=${limit}&offset=${offset}${
    filteredParams.toString() ? `&${filteredParams.toString()}` : ""
  }`;

  return useSWR<PaginatedWorkflowExecutionDto>(cacheKey, () => api.get(url));
};
