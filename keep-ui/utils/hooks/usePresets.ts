import { Preset } from "app/alerts/models";
import { useSession } from "next-auth/react";
import useSWR, { SWRConfiguration } from "swr";
import { getApiURL } from "utils/apiUrl";
import { fetcher } from "utils/fetcher";

export const usePresets = (options?: SWRConfiguration) => {
  const apiUrl = getApiURL();
  const { data: session } = useSession();

  return useSWR<Preset[]>(
    `${apiUrl}/preset`,
    async (url) => fetcher(url, session?.accessToken),
    options
  );
};
