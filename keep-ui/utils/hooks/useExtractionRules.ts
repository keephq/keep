import { ExtractionRule } from "app/extraction/model";
import { useSession } from "next-auth/react";
import useSWR, { SWRConfiguration } from "swr";
import { getApiURL } from "utils/apiUrl";
import { fetcher } from "utils/fetcher";

export const useExtractions = (
  options: SWRConfiguration = {
    revalidateOnFocus: false,
  }
) => {
  const apiUrl = getApiURL();
  const { data: session } = useSession();

  return useSWR<ExtractionRule[]>(
    () => (session ? `${apiUrl}/extraction` : null),
    (url) => fetcher(url, session?.accessToken),
    options
  );
};
