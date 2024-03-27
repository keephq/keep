import { AlertToWorkflowExecution } from "app/alerts/models";
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
