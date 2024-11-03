import { AILogs, AIStats } from "app/ai/model";
import { useSession } from "next-auth/react";
import useSWR, { SWRConfiguration } from "swr";
import { useApiUrl } from "./useConfig";
import { fetcher } from "utils/fetcher";

import { useWebsocket } from "./usePusher";
import { useCallback, useEffect } from "react";

export const useAIStats = (
  options: SWRConfiguration = {
    revalidateOnFocus: false,
  }
) => {
  const apiUrl = useApiUrl();
  const { data: session } = useSession();

  return useSWR<AIStats>(
    () => (session ? `${apiUrl}/ai/stats` : null),
    (url) => fetcher(url, session?.accessToken),
    options
  );
};

export const useUpdateAISettings = () => {
  const apiUrl = useApiUrl();
  const { data: session } = useSession();

  return async (settings: Record<string, any>) => {
    const response = await fetch(`${apiUrl}/ai/settings`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${session?.accessToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(settings),
    });

    return response.ok;
  };
}

export const usePollAILogs = (mutateAILogs: (logs: AILogs) => void) => {
  const { bind, unbind } = useWebsocket();
  const handleIncoming = useCallback(
    (data: AILogs) => {
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
