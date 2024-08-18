import { useSession } from "next-auth/react";
import { SWRConfiguration } from "swr";
import useSWRImmutable from "swr/immutable";
import { getApiURL } from "utils/apiUrl";
import { fetcher } from "utils/fetcher";
import { Tag } from "app/alerts/models";


export const useTags = (options: SWRConfiguration = {}) => {
  const apiUrl = getApiURL();
  const { data: session } = useSession();

  return useSWRImmutable<Tag[]>(
    () => (session ? `${apiUrl}/tags` : null),
    (url) => fetcher(url, session?.accessToken),
    options
  );
};
