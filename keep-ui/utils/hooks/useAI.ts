import { useWebsocket } from "./usePusher";
import { useCallback, useEffect } from "react";
import { useApi } from "@/shared/lib/hooks/useApi";
import { AIConfig, AILogs, AIStats } from "@/app/(keep)/ai/model";
import useSWR, { SWRConfiguration } from "swr";

export const useAIStats = (
  options: SWRConfiguration = {
    revalidateOnFocus: false,
  }
) => {
  const api = useApi();

  return useSWR<AIStats>(
    api.isReady() ? "/ai/stats" : null,
    (url) => api.get(url),
    options
  );
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

  const api = useApi();

  const updateAISettings = async (algorithm_id:string, settings: AIConfig): Promise<AIStats> => {
    const response = await api.put<AIStats>(`/ai/${algorithm_id}/settings`, settings);

    if (!response) {
      throw new Error("Failed to update AI settings");
    }
    return response;
  };
  
  return {
    updateAISettings: updateAISettings,
  };
}