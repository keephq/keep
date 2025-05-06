import { TimeFrameV2 } from "@/components/ui/DateRangePickerV2";
import { AlertDto, AlertsQuery, useAlerts } from "@/entities/alerts/model";
import { useAlertPolling } from "@/utils/hooks/useAlertPolling";
import { v4 as uuidv4 } from "uuid";
import { useEffect, useMemo, useRef, useState } from "react";

export interface AlertsTableDataQuery {
  searchCel: string;
  filterCel: string;
  limit: number;
  offset: number;
  sortOptions?: { sortBy: string; sortDirection?: "ASC" | "DESC" }[];
  timeFrame: TimeFrameV2;
}

export const useAlertsTableData = (query: AlertsTableDataQuery | undefined) => {
  const { useLastAlerts } = useAlerts();
  const [shouldRefreshDate, setShouldRefreshDate] = useState<boolean>(false);

  const [canRevalidate, setCanRevalidate] = useState<boolean>(false);
  const [dateRangeCel, setDateRangeCel] = useState<string | null>("");
  const [isPolling, setIsPolling] = useState<boolean>(false);
  const [alertsQueryState, setAlertsQueryState] = useState<
    AlertsQuery | undefined
  >(undefined);
  const incidentsQueryStateRef = useRef(alertsQueryState);
  const [facetsPanelRefreshToken, setFacetsPanelRefreshToken] = useState<
    string | undefined
  >(undefined);
  incidentsQueryStateRef.current = alertsQueryState;

  const isPaused = useMemo(() => {
    if (!query) {
      return false;
    }

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
  }, [query]);

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
    if (query?.timeFrame.type === "relative") {
      return `lastReceived >= '${new Date(
        new Date().getTime() - query.timeFrame.deltaMs
      ).toISOString()}'`;
    } else if (query?.timeFrame.type === "absolute") {
      return [
        `lastReceived >= '${query.timeFrame.start.toISOString()}'`,
        `lastReceived <= '${query.timeFrame.end.toISOString()}'`,
      ].join(" && ");
    }

    return null;
  };

  function updateAlertsCelDateRange() {
    const dateRangeCel = getDateRangeCel();

    setDateRangeCel(dateRangeCel);

    if (dateRangeCel) {
      return;
    }

    // if date does not change, just reload the data
    setFacetsPanelRefreshToken(uuidv4());
    mutateAlerts();
  }

  useEffect(() => updateAlertsCelDateRange(), [query?.timeFrame]);

  const { data: alertsChangeToken } = useAlertPolling(!isPaused);

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
        setIsPolling(true);
        updateAlertsCelDateRange();
      }
    }, refreshInterval);
    return () => clearInterval(interval);
  }, [isPaused, shouldRefreshDate]);

  useEffect(() => {
    setIsPolling(false);
  }, [JSON.stringify(query)]);

  const mainCelQuery = useMemo(() => {
    const filterArray = [query?.searchCel, dateRangeCel];

    return filterArray.filter(Boolean).join(" && ");
  }, [query?.searchCel, dateRangeCel]);

  useEffect(() => {
    if (!query) {
      setAlertsQueryState(undefined);
      return;
    }

    const alertsQuery: AlertsQuery = {
      limit: query.limit,
      offset: query.offset,
      sortOptions: query.sortOptions,
      cel: [mainCelQuery, query.filterCel].filter(Boolean).join(" && "),
    };

    (alertsQuery as any).source = "useAlertsTableData"; // TODO: TO REMOVE

    setAlertsQueryState(alertsQuery);
  }, [
    mainCelQuery,
    query?.filterCel,
    query?.sortOptions,
    query?.limit,
    query?.offset,
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
    revalidateOnMount: true,
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
    mutateAlerts,
    facetsPanelRefreshToken,
  };
};
