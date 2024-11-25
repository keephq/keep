import { useConfig } from "@/utils/hooks/useConfig";
import { useHydratedSession as useSession } from "@/shared/lib/hooks/useHydratedSession";
import { useMemo } from "react";
import { ApiClient } from "../api/ApiClient";

export function useApi() {
  const { data: config } = useConfig();
  const { data: session } = useSession();

  const api = useMemo(() => {
    return new ApiClient(session, config, false);
  }, [session, config]);

  return api;
}
