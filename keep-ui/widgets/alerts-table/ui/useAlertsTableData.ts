import { TimeFrameV2 } from "@/components/ui/DateRangePickerV2";
import { AlertDto, AlertsQuery, useAlerts } from "@/entities/alerts/model";
import { useAlertPolling } from "@/utils/hooks/useAlertPolling";

import { useEffect, useMemo, useRef, useState } from "react";

export interface AlertsTableDataQuery {
  limit: number;
  offset: number;
  sortOptions?: { sortBy: string; sortDirection?: "ASC" | "DESC" }[];
  filterCel: string;
  timeFrame: TimeFrameV2;
}

export const useAlertsTableData = (query: AlertsTableDataQuery) => {
  const { useLastAlerts } = useAlerts();
  const [shouldRefreshDate, setShouldRefreshDate] = useState<boolean>(false);

  const [canRevalidate, setCanRevalidate] = useState<boolean>(false);
  const [dateRangeCel, setDateRangeCel] = useState<string | null>("");
  const [isPolling, setIsPolling] = useState<boolean>(false);
  const [alertsQueryState, setAlertsQueryState] = useState<
    AlertsQuery | undefined
  >(undefined);
  const incidentsQueryStateRef = useRef(alertsQueryState);
  incidentsQueryStateRef.current = alertsQueryState;

  const isPaused = useMemo(() => {
    switch (query.timeFrame.type) {
      case "absolute":
        return false;
      case "relative":
        return query.timeFrame.isPaused;
      case "all-time":
        return query.timeFrame.isPaused;
      default:
        return true;
    }
  }, [query.timeFrame]);

  useEffect(() => {
    if (canRevalidate) {
      return;
    }

    const timeout = setTimeout(() => {
      setCanRevalidate(true);
    }, 3000);
    return () => clearTimeout(timeout);
  }, [canRevalidate]);

  const getDateRangeCel = () => {
    const currentDate = new Date();

    if (query.timeFrame.type === "relative") {
      return `lastReceived >= '${new Date(
        currentDate.getTime() - query.timeFrame.deltaMs
      ).toISOString()}'`;
    } else if (query.timeFrame.type === "absolute") {
      return [
        `lastReceived >= '${query.timeFrame.start.toISOString()}'`,
        `lastReceived <= '${query.timeFrame.end.toISOString()}'`,
      ].join(" && ");
    }

    return null;
  };

  function updateAlertsCelDateRange() {
    const dateRangeCel = getDateRangeCel();
    setIsPolling(true);

    setDateRangeCel(dateRangeCel);

    if (dateRangeCel) {
      return;
    }

    // if date does not change, just reload the data
    mutateAlerts();
  }

  useEffect(() => updateAlertsCelDateRange(), [query.timeFrame]);

  const { data: alertsChangeToken } = useAlertPolling(isPaused);

  useEffect(() => {
    // When refresh token comes, this code allows polling for certain time and then stops.
    // Will start polling again when new refresh token comes.
    // Why? Because events are throttled on BE side but we want to refresh the data frequently
    // when keep gets ingested with data, and it requires control when to refresh from the UI side.
    if (alertsChangeToken) {
      setShouldRefreshDate(true);
      const timeout = setTimeout(() => {
        setShouldRefreshDate(false);
      }, 15000);
      return () => clearTimeout(timeout);
    }
  }, [alertsChangeToken]);

  useEffect(() => {
    if (isPaused) {
      return;
    }
    // so that gap between poll is 2x of query time and minimum 3sec
    const refreshInterval = Math.max((queryTimeInSeconds || 1000) * 2, 6000);
    const interval = setInterval(() => {
      if (!isPaused && shouldRefreshDate) {
        updateAlertsCelDateRange();
      }
    }, refreshInterval);
    return () => clearInterval(interval);
  }, [isPaused, shouldRefreshDate]);

  const mainCelQuery = useMemo(() => {
    const filterArray = ["is_candidate == false", dateRangeCel];

    return filterArray.filter(Boolean).join(" && ");
  }, [dateRangeCel]);

  useEffect(() => {
    setAlertsQueryState({
      limit: query.limit,
      offset: query.offset,
      sortOptions: query.sortOptions,
      cel: [mainCelQuery, query.filterCel].filter(Boolean).join(" && "),
    });
  }, [
    query.sortOptions,
    query.filterCel,
    query.limit,
    query.offset,
    mainCelQuery,
  ]);

  const {
    data: alerts,
    totalCount,
    isLoading: alertsLoading,
    mutate: mutateAlerts,
    error: alertsError,
    queryTimeInSeconds,
  } = useLastAlerts(alertsQueryState, {
    revalidateOnFocus: false,
    revalidateOnMount: false,
  });

  const [alertsToReturn, setAlertsToReturn] = useState<
    AlertDto[] | undefined
  >();
  useEffect(() => {
    if (!alerts) {
      return;
    }

    if (!isPaused) {
      if (!alertsLoading) {
        setAlertsToReturn(alerts);
      }

      return;
    }

    setAlertsToReturn(alertsLoading ? undefined : alerts);
  }, [isPaused, alertsLoading, alerts]);

  return {
    alerts: alertsToReturn,
    totalCount,
    alertsLoading: !isPolling && alertsLoading,
    facetsCel: mainCelQuery,
    alertsChangeToken: alertsChangeToken,
    alertsError: alertsError,
  };
};
