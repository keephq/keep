import { ExtractionRule } from "@/app/(keep)/extraction/model";
import { useSession } from "next-auth/react";
import useSWR, { SWRConfiguration } from "swr";
import { useApiUrl } from "./useConfig";
import { fetcher } from "utils/fetcher";

export const useExtractions = (
  options: SWRConfiguration = {
    revalidateOnFocus: false,
  }
) => {
  const apiUrl = useApiUrl();
  const { data: session } = useSession();

  return useSWR<ExtractionRule[]>(
    () => (session ? `${apiUrl}/extraction` : null),
    (url) => fetcher(url, session?.accessToken),
    options
  );
};
