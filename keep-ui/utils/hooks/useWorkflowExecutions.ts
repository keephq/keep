import { AlertToWorkflowExecution } from "@/app/(keep)/alerts/models";
import {
  PaginatedWorkflowExecutionDto,
  WorkflowExecution,
} from "@/app/(keep)/workflows/builder/types";
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
  tab: number = 0,
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
  tab = searchParams?.get("tab") ? Number(searchParams?.get("tab")) : tab;
  limit = limit > 100 ? 50 : limit;
  limit = limit <= 0 ? 25 : limit;
  offset = offset < 0 ? 0 : offset;
  tab = tab < 0 ? 0 : tab;
  tab = tab > 3 ? 3 : tab;

  return useSWR<PaginatedWorkflowExecutionDto>(
    api.isReady()
      ? `/workflows/${workflowId}/runs?v2=true&tab=${tab}&limit=${limit}&offset=${offset}${
          searchParams ? `&${searchParams.toString()}` : ""
        }`
      : null,
    api.get
  );
};

export const useWorkflowExecution = (
  workflowId: string,
  workflowExecutionId: string
) => {
  const api = useApi();

  return useSWR<WorkflowExecution>(
    api.isReady()
      ? `/workflows/${workflowId}/runs/${workflowExecutionId}`
      : null,
    api.get
  );
};
