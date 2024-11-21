import { useHydratedSession as useSession } from "@/shared/lib/hooks/useHydratedSession";
import { SWRConfiguration } from "swr";
import useSWRImmutable from "swr/immutable";
import { useApiUrl } from "./useConfig";
import { fetcher } from "utils/fetcher";
import { Tag } from "@/app/(keep)/alerts/models";

export const useTags = (options: SWRConfiguration = {}) => {
  const apiUrl = useApiUrl();
  const { data: session } = useSession();

  return useSWRImmutable<Tag[]>(
    () => (session ? `${apiUrl}/tags` : null),
    (url) => fetcher(url, session?.accessToken),
    options
  );
};
