import { MappingRule } from "@/app/(keep)/mapping/models";
import { useHydratedSession as useSession } from "@/shared/lib/hooks/useHydratedSession";
import useSWR, { SWRConfiguration } from "swr";
import { useApiUrl } from "./useConfig";
import { fetcher } from "utils/fetcher";

export const useMappings = (
  options: SWRConfiguration = {
    revalidateOnFocus: false,
  }
) => {
  const apiUrl = useApiUrl();
  const { data: session } = useSession();

  return useSWR<MappingRule[]>(
    () => (session ? `${apiUrl}/mapping` : null),
    (url) => fetcher(url, session?.accessToken),
    options
  );
};
