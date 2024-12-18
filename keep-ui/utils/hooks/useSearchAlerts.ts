import useSWR, { SWRConfiguration } from "swr";
import { AlertDto } from "@/app/(keep)/alerts/models";
import { useDebouncedValue } from "./useDebouncedValue";
import { RuleGroupType, formatQuery } from "react-querybuilder";
import { useApi } from "@/shared/lib/hooks/useApi";
import { useMemo, useEffect, useRef } from "react";

export const useSearchAlerts = (
  args: { query: RuleGroupType; timeframe: number },
  options?: SWRConfiguration
) => {
  const api = useApi();

  // Create a stable key for our query
  const argsString = useMemo(
    () => JSON.stringify(args),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [args.timeframe, JSON.stringify(args.query)]
  );

  const previousArgsStringRef = useRef<string>(argsString);

  const [debouncedArgsString] = useDebouncedValue(argsString, 2000);
  const debouncedArgs = JSON.parse(debouncedArgsString);

  const doesTimeframExceed14Days = Math.floor(args.timeframe / 86400) > 13;

  const key =
    api.isReady() && !doesTimeframExceed14Days
      ? ["/alerts/search", debouncedArgsString]
      : null;

  const { mutate, ...rest } = useSWR<AlertDto[]>(
    key,
    async () =>
      api.post(`/alerts/search`, {
        query: {
          cel_query: formatQuery(debouncedArgs.query, "cel"),
          sql_query: formatQuery(debouncedArgs.query, "parameterized_named"),
        },
        timeframe: debouncedArgs.timeframe,
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
    if (argsString !== previousArgsStringRef.current) {
      mutate(undefined, false);
      previousArgsStringRef.current = argsString;
    }
  }, [argsString, mutate]); // Not debouncedArgsString

  return { ...rest, mutate };
};
