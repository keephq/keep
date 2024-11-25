import useSWR, { SWRConfiguration } from "swr";
import { AlertDto } from "@/app/(keep)/alerts/models";
import { useDebouncedValue } from "./useDebouncedValue";
import { RuleGroupType, formatQuery } from "react-querybuilder";
import { useApi } from "@/shared/lib/hooks/useApi";

export const useSearchAlerts = (
  args: { query: RuleGroupType; timeframe: number },
  options?: SWRConfiguration
) => {
  const api = useApi();

  const [debouncedArgs] = useDebouncedValue(args, 2000);
  const doesTimeframExceed14Days = Math.floor(args.timeframe / 86400) > 13;
  const { timeframe: debouncedTimeframe, query: debouncedRules } =
    debouncedArgs;

  return useSWR<AlertDto[]>(
    () => (doesTimeframExceed14Days ? false : debouncedArgs),
    async () =>
      api.post(`/alerts/search`, {
        query: {
          cel_query: formatQuery(debouncedRules, "cel"),
          sql_query: formatQuery(debouncedRules, "parameterized_named"),
        },
        timeframe: debouncedTimeframe,
      }),
    options
  );
};
