import { User } from "@/app/(keep)/settings/models";
import { useHydratedSession as useSession } from "@/shared/lib/hooks/useHydratedSession";
import { SWRConfiguration } from "swr";
import useSWRImmutable from "swr/immutable";
import { useApiUrl } from "./useConfig";
import { fetcher } from "utils/fetcher";

export const useUsers = (options: SWRConfiguration = {}) => {
  const apiUrl = useApiUrl();
  const { data: session } = useSession();

  return useSWRImmutable<User[]>(
    () => (session ? `${apiUrl}/auth/users` : null),
    (url) => fetcher(url, session?.accessToken),
    options
  );
};
