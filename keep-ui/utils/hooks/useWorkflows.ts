import { Workflow } from "app/workflows/models";
import { useSession } from "next-auth/react";
import { SWRConfiguration } from "swr";
import { getApiURL } from "../apiUrl";
import { fetcher } from "../fetcher";
import useSWRImmutable from "swr/immutable";

export const useWorkflows = (options: SWRConfiguration = {}) => {
  const { data: session } = useSession();
  const apiUrl = getApiURL();

  return useSWRImmutable<Workflow[]>(
    () => (session ? `${apiUrl}/workflows` : null),
    (url) => fetcher(url, session?.accessToken),
    options
  );
};
