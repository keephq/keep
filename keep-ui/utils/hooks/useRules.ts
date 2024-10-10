import { useSession } from "next-auth/react";
import useSWR, { SWRConfiguration } from "swr";
import { getApiURL } from "utils/apiUrl";
import { fetcher } from "utils/fetcher";
import { useState, useEffect, useCallback } from "react";
import Pusher from "pusher-js";
import { useWebsocket } from "./usePusher";


export type Rule = {
  id: string;
  name: string;
  item_description: string | null;
  group_description: string | null;
  grouping_criteria: string[];
  definition_cel: string;
  definition: { sql: string; params: {} };
  timeframe: number;
  timeunit: "minutes" | "seconds" | "hours" | "days";
  created_by: string;
  creation_time: string;
  tenant_id: string;
  updated_by: string | null;
  update_time: string | null;
  require_approve: boolean;
  resolve_on: "all" | "first" | "last" | "never";
  distribution: { [group: string]: { [timestamp: string]: number } };
  incidents: number;
};

export type AIGeneratedRule = {
  ShortRuleName: string;
  CELRule: string;
  Timeframe: string;
  GroupBy: string[];
  ChainOfThought: string;
  WhyTooGeneral: string;
  WhyTooSpecific: string;
  Score: number;
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


export const useRulePusherUpdates = () => {
  const { bind, unbind } = useWebsocket();
  const [serverGenRules, setServerGenRules] = useState([]);

  const handleIncoming = useCallback((incoming: any) => {
    setServerGenRules(incoming);
  }, []);

  useEffect(() => {
    bind("rules-aigen-created", handleIncoming);
    return () => {
      unbind("rules-aigen-created", handleIncoming);
    };
  }, [bind, unbind, handleIncoming]);

  return { data: serverGenRules };
};




export const useGenRules = () => {
  const apiUrl = getApiURL();
  const { data: session } = useSession();

  const { data, error, isValidating, mutate } = useSWR(
    () => session ? `${apiUrl}/rules/gen_rules` : null,
    async (url) => {
      const response = await fetcher(url, session?.accessToken);
      return response;
    },
    {
      revalidateOnFocus: false,
      revalidateOnReconnect: false,
      refreshInterval: 0,
    }
  );

  const triggerGenRules = () => {
    mutate();
  };

  return {
    data,
    error,
    isLoading: isValidating,
    triggerGenRules,
  };
};
