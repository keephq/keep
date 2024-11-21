import { AILogs, AIStats } from "@/app/(keep)/ai/model";
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

  return useSWR<AIStats>(
    () => (session ? `${apiUrl}/ai/stats` : null),
    (url) => fetcher(url, session?.accessToken),
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
