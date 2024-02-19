import { MappingRule } from "app/mapping/models";
import { getServerSession } from "next-auth";
import { authOptions } from "pages/api/auth/[...nextauth]";
import useSWR, { SWRConfiguration } from "swr";
import { getApiURL } from "utils/apiUrl";
import { fetcher } from "utils/fetcher";

export const useMappings = async (options: SWRConfiguration = {}) => {
  const apiUrl = getApiURL();
  const session = await getServerSession(authOptions);

  return useSWR<MappingRule[]>(
    () => (session ? `${apiUrl}/mapping` : null),
    (url) => fetcher(url, session?.accessToken),
    options
  );
};
