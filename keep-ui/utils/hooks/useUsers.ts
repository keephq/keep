import { User } from "app/settings/models";
import { useSession } from "next-auth/react";
import useSWR, { SWRConfiguration } from "swr";
import { getApiURL } from "utils/apiUrl";
import { fetcher } from "utils/fetcher";

export const useUsers = (options?: SWRConfiguration) => {
  const apiUrl = getApiURL();
  const { data: session } = useSession();

  return useSWR<User[]>(
    () => (session ? `${apiUrl}/settings/users` : null),
    (url) => fetcher(url, session?.accessToken),
    options
  );
};
