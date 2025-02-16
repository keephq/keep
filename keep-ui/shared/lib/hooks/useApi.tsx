import { useConfig } from "@/utils/hooks/useConfig";
import { useHydratedSession as useSession } from "@/shared/lib/hooks/useHydratedSession";
import { useMemo } from "react";
import { ApiClient } from "@/shared/api/ApiClient";
import { GuestSession } from "@/types/auth";

export function useApi() {
  const { data: config } = useConfig();
  const { data: user_session, status } = useSession();
  const api = useMemo(() => {
    const session = status === "unauthenticated" ? {
      accessToken: "unauthenticated"
    } as GuestSession : user_session;

    console.log('Created session:', session);

    return new ApiClient(session, config);
  }, [status, user_session?.accessToken, config]);

  return api;
}
