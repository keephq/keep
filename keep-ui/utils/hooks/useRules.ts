import { useSession } from "next-auth/react";
import useSWR, { SWRConfiguration } from "swr";
import { getApiURL } from "utils/apiUrl";
import { fetcher } from "utils/fetcher";

export type Rule = {
  id: string;
  name: string;
  item_description: string | null;
  group_description: string | null;
  grouping_criteria: string[];
  definition_cel: string;
  definition: { sql: string; params: {} };
  timeframe: number;
  created_by: string;
  creation_time: string;
  tenant_id: string;
  updated_by: string | null;
  update_time: string | null;
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
