import { AIStats } from "app/ai/model";
import { useSession } from "next-auth/react";
import useSWR, { SWRConfiguration } from "swr";
import { getApiURL } from "utils/apiUrl";
import { fetcher } from "utils/fetcher";

export const useAIStats = (
  options: SWRConfiguration = {
    revalidateOnFocus: false,
  }
) => {
  const apiUrl = getApiURL();
  const { data: session } = useSession();

  return useSWR<AIStats>(
    () => (session ? `${apiUrl}/ai/stats` : null),
    (url) => fetcher(url, session?.accessToken),
    options
  );
};
