import useSWR, { SWRConfiguration } from "swr";
import { AlertDto } from "@/app/(keep)/alerts/models";
import { useHydratedSession as useSession } from "@/shared/lib/hooks/useHydratedSession";
import { useApiUrl } from "./useConfig";
import { fetcher } from "utils/fetcher";
import { useDebouncedValue } from "./useDebouncedValue";
import { RuleGroupType, formatQuery } from "react-querybuilder";
import { useMemo, useEffect } from "react";

export const useSearchAlerts = (
  args: { query: RuleGroupType; timeframe: number },
  options?: SWRConfiguration
) => {
  const apiUrl = useApiUrl();
  const { data: session } = useSession();

  // Create a stable key for our query
  const argsString = useMemo(
    () => JSON.stringify(args),
    [args.timeframe, JSON.stringify(args.query)]
  );

  const [debouncedArgsString] = useDebouncedValue(argsString, 2000);
  const debouncedArgs = JSON.parse(debouncedArgsString);

  const doesTimeframExceed14Days = Math.floor(args.timeframe / 86400) > 13;

  const key = doesTimeframExceed14Days
    ? null
    : ["/alerts/search", debouncedArgsString];

  const swr = useSWR<AlertDto[]>(
    key,
    async () =>
      fetcher(`${apiUrl}/alerts/search`, session?.accessToken, {
        headers: {
          Authorization: `Bearer ${session?.accessToken}`,
          "Content-type": "application/json",
        },
        method: "POST",
        body: JSON.stringify({
          query: {
            cel_query: formatQuery(debouncedArgs.query, "cel"),
            sql_query: formatQuery(debouncedArgs.query, "parameterized_named"),
          },
          timeframe: debouncedArgs.timeframe,
        }),
      }),
    {
      ...options,
      keepPreviousData: false,
      revalidateOnFocus: false,
      revalidateOnReconnect: false,
    }
  );

  // Clear data immediately when query changes, before debounce
  useEffect(() => {
    swr.mutate(undefined, false);
  }, [argsString]); // Not debouncedArgsString

  return swr;
};
