import useSWR, { SWRConfiguration } from "swr";
import { AlertDto } from "app/alerts/models";
import { useSession } from "next-auth/react";
import { getApiURL } from "utils/apiUrl";
import { fetcher } from "utils/fetcher";
import { useDebouncedValue } from "./useDebouncedValue";
import { RuleGroupType, formatQuery } from "react-querybuilder";

export const useSearchAlerts = (
  args: { query: RuleGroupType; timeframe: number },
  options?: SWRConfiguration
) => {
  const apiUrl = getApiURL();
  const { data: session } = useSession();

  const [debouncedArgs] = useDebouncedValue(args, 2000);
  const doesTimeframExceed14Days = Math.floor(args.timeframe / 86400) > 13;
  const { timeframe: debouncedTimeframe, query: debouncedRules } =
    debouncedArgs;

  return useSWR<AlertDto[]>(
    () => (doesTimeframExceed14Days ? false : debouncedArgs),
    async () =>
      fetcher(`${apiUrl}/alerts/search`, session?.accessToken, {
        headers: {
          Authorization: `Bearer ${session?.accessToken}`,
          "Content-type": "application/json",
        },
        method: "POST",
        body: JSON.stringify({
          query: formatQuery(debouncedRules, "cel"),
          timeframe: debouncedTimeframe,
        }),
      }),
    options
  );
};
