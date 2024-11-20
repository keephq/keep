import { Workflow } from "@/app/(keep)/workflows/models";
import { useSession } from "next-auth/react";
import { SWRConfiguration } from "swr";
import { useApiUrl } from "./useConfig";
import { fetcher } from "../fetcher";
import useSWRImmutable from "swr/immutable";

export const useWorkflows = (options: SWRConfiguration = {}) => {
  const { data: session } = useSession();
  const apiUrl = useApiUrl();

  return useSWRImmutable<Workflow[]>(
    () => (session ? `${apiUrl}/workflows` : null),
    (url) => fetcher(url, session?.accessToken),
    options
  );
};
