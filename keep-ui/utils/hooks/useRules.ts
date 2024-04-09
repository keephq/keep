import { useSession } from "next-auth/react";
import useSWR, { SWRConfiguration } from "swr";
import { getApiURL } from "utils/apiUrl";
import { fetcher } from "utils/fetcher";

export type Rule = {
  id: string;
  name: string;
  definition: string;
  definition_cel: string;
  timeframe: number;
  created_by: string;
  creation_time: string;
  updated_by: string;
  update_time: string;
  distribution: { [group: string]: { [timestamp: string]: number } };
};

export const useRules = (options?: SWRConfiguration) => {
  const apiUrl = getApiURL();
  const { data: session } = useSession();

  return useSWR<Rule[]>(
    () => (session ? `${apiUrl}/rules` : null),
    async (url) => fetcher(url, session?.accessToken),
    options
  );
};
