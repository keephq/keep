import { AILogs, AIStats } from "@/app/(keep)/ai/model";
import useSWR, { SWRConfiguration } from "swr";

import { useWebsocket } from "./usePusher";
import { useCallback, useEffect } from "react";
import { useApi } from "@/shared/lib/hooks/useApi";

export const useAIStats = (
  options: SWRConfiguration = {
    revalidateOnFocus: false,
  }
) => {
  const api = useApi();

  return useSWR<AIStats>(api.isReady() ? "/ai/stats" : null, api.get, options);
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
