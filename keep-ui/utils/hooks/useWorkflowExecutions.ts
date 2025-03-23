import { AlertToWorkflowExecution } from "@/entities/alerts/model";
import {
  PaginatedWorkflowExecutionDto,
  WorkflowExecutionDetail,
} from "@/shared/api/workflow-executions";
import { useSearchParams } from "next/navigation";
import useSWR, { SWRConfiguration } from "swr";
import { useApi } from "@/shared/lib/hooks/useApi";

export const useWorkflowExecutions = (
  options: SWRConfiguration = {
    revalidateOnFocus: false,
  }
) => {
  const api = useApi();

  return useSWR<AlertToWorkflowExecution[]>(
    api.isReady() ? "/workflows/executions" : null,
    (url) => api.get(url),
    options
  );
};

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

  return useSWR<PaginatedWorkflowExecutionDto>(
    api.isReady()
      ? `/workflows/${workflowId}/runs?v2=true&limit=${limit}&offset=${offset}${
          filteredParams.toString() ? `&${filteredParams.toString()}` : ""
        }`
      : null,
    (url: string) => api.get(url)
  );
};

export const useWorkflowExecution = (
  workflowId: string,
  workflowExecutionId: string
) => {
  const api = useApi();

  return useSWR<WorkflowExecutionDetail>(
    api.isReady()
      ? `/workflows/${workflowId}/runs/${workflowExecutionId}`
      : null,
    (url: string) => api.get(url)
  );
};
