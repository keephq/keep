import { AlertToWorkflowExecution } from "app/alerts/models";
import {
  PaginatedWorkflowExecutionDto,
  WorkflowExecution,
} from "app/workflows/builder/types";
import { useHydratedSession as useSession } from "@/shared/lib/hooks/useHydratedSession";
import { useSearchParams } from "next/navigation";
import useSWR, { SWRConfiguration } from "swr";
import { useApiUrl } from "./useConfig";
import { fetcher } from "utils/fetcher";

export const useWorkflowExecutions = (
  options: SWRConfiguration = {
    revalidateOnFocus: false,
  }
) => {
  const apiUrl = useApiUrl();
  const { data: session } = useSession();

  return useSWR<AlertToWorkflowExecution[]>(
    () => (session ? `${apiUrl}/workflows/executions` : null),
    async (url) => fetcher(url, session?.accessToken),
    options
  );
};

export const useWorkflowExecutionsV2 = (
  workflowId: string,
  tab: number = 0,
  limit: number = 25,
  offset: number = 0
) => {
  const apiUrl = useApiUrl();
  const { data: session } = useSession();
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
    () =>
      session
        ? `${apiUrl}/workflows/${workflowId}/runs?v2=true&tab=${tab}&limit=${limit}&offset=${offset}${
            searchParams ? `&${searchParams.toString()}` : ""
          }`
        : null,
    (url: string) => fetcher(url, session?.accessToken)
  );
};

export const useWorkflowExecution = (
  workflowId: string,
  workflowExecutionId: string
) => {
  const apiUrl = useApiUrl();
  const { data: session } = useSession();

  return useSWR<WorkflowExecution>(
    () =>
      session
        ? `${apiUrl}/workflows/${workflowId}/runs/${workflowExecutionId}`
        : null,
    (url: string) => fetcher(url, session?.accessToken)
  );
};
