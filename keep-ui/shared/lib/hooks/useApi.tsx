import { useConfig } from "@/utils/hooks/useConfig";
import { useHydratedSession } from "./useHydratedSession";
import { useMemo } from "react";
import { createApiClient, updateClientInstance } from "@/shared/api/client";
import { GuestSession } from "@/types/auth";

export function useApi() {
  const { data: config } = useConfig();
  const { data: user_session, status } = useHydratedSession();

  const api = useMemo(() => {
    const session =
      status === "unauthenticated"
        ? ({ accessToken: "unauthenticated" } as GuestSession)
        : user_session;

    const instance = createApiClient(session, config);
    // Update the shared instance
    updateClientInstance(instance);
    return instance;
  }, [status, user_session?.accessToken, config]);

  return api;
}
