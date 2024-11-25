import { MappingRule } from "@/app/(keep)/mapping/models";
import { useHydratedSession as useSession } from "@/shared/lib/hooks/useHydratedSession";
import useSWR, { SWRConfiguration } from "swr";
import { useApi } from "@/shared/lib/hooks/useApi";

export const useMappings = (
  options: SWRConfiguration = {
    revalidateOnFocus: false,
  }
) => {
  const api = useApi();

  return useSWR<MappingRule[]>(
    api.isReady() ? "/mapping" : null,
    api.get,
    options
  );
};
