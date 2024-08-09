import { AIStats } from "app/ai/model";
import { useSession } from "next-auth/react";
import useSWR, { SWRConfiguration } from "swr";
import { getApiURL } from "utils/apiUrl";
import { fetcher } from "utils/fetcher";

import { useWebsocket } from "./usePusher";
import { useCallback, useEffect } from "react";


export const useAIStats = (
  options: SWRConfiguration = {
    revalidateOnFocus: false,
  }
) => {
  const apiUrl = getApiURL();
  const { data: session } = useSession();

  return useSWR<AIStats>(
    () => (session ? `${apiUrl}/ai/stats` : null),
    (url) => fetcher(url, session?.accessToken),
    options
  );
};

export const usePollAILogs = (mutateAILogs: any) => {
  const { bind, unbind } = useWebsocket();
  const handleIncoming = useCallback(
    (data: any) => {
      mutateAILogs(data);
    },
    [mutateAILogs]
  );

  useEffect(() => {
    bind("ai-logs-change", handleIncoming);
    return () => {
      unbind("ai-logs-change", handleIncoming);
    };
  }, [bind, unbind, handleIncoming]);
};