import useSWR, { SWRConfiguration } from "swr";
import { AlertDto } from "@/app/(keep)/alerts/models";
import { useHydratedSession as useSession } from "@/shared/lib/hooks/useHydratedSession";
import { useApiUrl } from "./useConfig";
import { fetcher } from "utils/fetcher";
import { useDebouncedValue } from "./useDebouncedValue";
import { RuleGroupType, formatQuery } from "react-querybuilder";

export const useSearchAlerts = (
  args: { query: RuleGroupType; timeframe: number },
  options?: SWRConfiguration
) => {
  const apiUrl = useApiUrl();
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
          query: {
            cel_query: formatQuery(debouncedRules, "cel"),
            sql_query: formatQuery(debouncedRules, "parameterized_named"),
          },
          timeframe: debouncedTimeframe,
        }),
      }),
    options
  );
};
