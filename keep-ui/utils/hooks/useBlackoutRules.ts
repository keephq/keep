import { BlackoutRule } from "app/blackout/model";
import { useSession } from "next-auth/react";
import useSWR, { SWRConfiguration } from "swr";
import { getApiURL } from "utils/apiUrl";
import { fetcher } from "utils/fetcher";

export const useBlackouts = (
  options: SWRConfiguration = {
    revalidateOnFocus: false,
  }
) => {
  const apiUrl = getApiURL();
  const { data: session } = useSession();

  return useSWR<BlackoutRule[]>(
    () => (session ? `${apiUrl}/blackout` : null),
    (url) => fetcher(url, session?.accessToken),
    options
  );
};
