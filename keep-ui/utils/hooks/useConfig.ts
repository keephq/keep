import { useSession } from "next-auth/react";
import useSWRImmutable from "swr/immutable";
import { InternalConfig } from "types/internal-config";
import { fetcher } from "utils/fetcher";

export const useConfig = () => {
  const { data: session } = useSession();

  return useSWRImmutable<InternalConfig>("/api/config", () =>
    fetcher("/api/config", session?.accessToken)
  );
};
