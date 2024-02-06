import { User } from "app/settings/models";
import { useSession } from "next-auth/react";
import useSWR, { SWRConfiguration } from "swr";
import { getApiURL } from "utils/apiUrl";
import { fetcher } from "utils/fetcher";

export const useUsers = (
  options: SWRConfiguration = {
    dedupingInterval: 10000,
    revalidateOnFocus: false,
  }
) => {
  const apiUrl = getApiURL();
  const { data: session } = useSession();

  return useSWR<User[]>(
    () => (session ? `${apiUrl}/users` : null),
    (url) => fetcher(url, session?.accessToken),
    options
  );
};
