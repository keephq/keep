import { User } from "app/settings/models";
import { useSession } from "next-auth/react";
import useSWR from "swr";
import { getApiURL } from "utils/apiUrl";
import { fetcher } from "utils/fetcher";

export const useUsers = () => {
  const apiUrl = getApiURL();
  const { data: session } = useSession();

  return useSWR<User[]>(
    `${apiUrl}/settings/users`,
    (url) => fetcher(url, session?.accessToken),
    { revalidateOnFocus: false }
  );
};
