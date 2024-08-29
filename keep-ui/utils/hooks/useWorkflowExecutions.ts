import { AlertToWorkflowExecution } from "app/alerts/models";
import { PaginatedWorkflowExecutionDto, WorkflowExecution } from "app/workflows/builder/types";
import { useSession } from "next-auth/react";
import useSWR, { SWRConfiguration } from "swr";
import { getApiURL } from "utils/apiUrl";
import { fetcher } from "utils/fetcher";

export const useWorkflowExecutions = (options?: SWRConfiguration) => {
  const apiUrl = getApiURL();
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
  offset: number = 0,
) => {
  console.log("entering this", tab, limit, offset);
  const apiUrl = getApiURL();
  const { data: session } = useSession();
  return useSWR<PaginatedWorkflowExecutionDto>(
    () => (session ? `${apiUrl}/workflows/${workflowId}?v2=true&tab=${tab}&limit=${limit}&offset=${offset}` : null),
    (url: string) => fetcher(url, session?.accessToken)
  );
};
