import { Workflow } from "app/workflows/models";
import { useSession } from "next-auth/react";
import useSWR, { SWRConfiguration } from "swr";
import { getApiURL } from "../apiUrl";
import { fetcher } from "../fetcher";

export const useWorkflows = (
  options: SWRConfiguration = {
    revalidateOnFocus: false,
    revalidateOnMount: false,
  }
) => {
  const { data: session } = useSession();
  const apiUrl = getApiURL();

  return useSWR<Workflow[]>(
    () => (session ? `${apiUrl}/workflows` : null),
    (url) => fetcher(url, session?.accessToken),
    options
  );
};
