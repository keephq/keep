import { AILogs, AIStats, AIConfig } from "@/app/(keep)/ai/model";
import { useHydratedSession as useSession } from "@/shared/lib/hooks/useHydratedSession";
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

  const { data, error, mutate } = useSWR<AIStats>(
    () => (session ? `${apiUrl}/ai/stats` : null),
    (url) => fetcher(url, session?.accessToken),
    options
  );

  return {
    data,
    isLoading: !data && !error,
    error,
    refetch: mutate,
  };
};

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

type UseAIActionsValue = {
  updateAISettings: (algorithm_id: string, settings: AIConfig) => Promise<AIStats>;
};

export function UseAIActions(): UseAIActionsValue {

  const apiUrl = useApiUrl();
  const { data: session } = useSession();

  const updateAISettings = async (algorithm_id:string, settings: AIConfig): Promise<AIStats> => {
    const response = await fetch(`${apiUrl}/ai/${algorithm_id}/settings`, {
      method: "PUT",
      headers: {
        Authorization: `Bearer ${session?.accessToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(settings),
    });

    if (!response.ok) {
      throw new Error('Failed to update AI settings');
    }

    return response.json();
  };
  
  return {
    updateAISettings: updateAISettings,
  };
}