import { TimeFrameV2 } from "@/components/ui/DateRangePickerV2";
import { AlertDto, AlertsQuery, useAlerts } from "@/entities/alerts/model";
import { useApi } from "@/shared/lib/hooks/useApi";
import { useAlertPolling } from "@/utils/hooks/useAlertPolling";
import { toDateObjectWithFallback } from "@/utils/helpers";
import { v4 as uuidv4 } from "uuid";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

export interface AlertsTableDataQuery {
  searchCel: string;
  filterCel: string;
  limit: number;
  offset: number;
  sortOptions?: { sortBy: string; sortDirection?: "ASC" | "DESC" }[];
  timeFrame: TimeFrameV2;
}

function getDateRangeCel(timeFrame: TimeFrameV2 | null): string | null {
  if (timeFrame === null) {
    return null;
  }

  if (timeFrame.type === "relative") {
    return `lastReceived >= '${new Date(
      new Date().getTime() - timeFrame.deltaMs
    ).toISOString()}'`;
  } else if (timeFrame.type === "absolute") {
    return [
      `lastReceived >= '${timeFrame.start.toISOString()}'`,
      `lastReceived <= '${timeFrame.end.toISOString()}'`,
    ].join(" && ");
  }

  return "";
}

function getAlertSortValue(
  alert: AlertDto,
  sortBy: string
): string | number {
  const value = (alert as unknown as Record<string, unknown>)[sortBy];
  if (value instanceof Date) {
    return value.getTime();
  }
  if (typeof value === "string") {
    return value.toLowerCase();
  }
  if (typeof value === "number") {
    return value;
  }
  return "";
}

function sortAlerts(
  alerts: AlertDto[],
  sortOptions?: { sortBy: string; sortDirection?: "ASC" | "DESC" }[]
): AlertDto[] {
  if (!sortOptions?.length) {
    return alerts;
  }

  const [{ sortBy, sortDirection = "ASC" }] = sortOptions;
  const direction = sortDirection === "DESC" ? -1 : 1;

  return [...alerts].sort((left, right) => {
    const leftValue = getAlertSortValue(left, sortBy);
    const rightValue = getAlertSortValue(right, sortBy);

    if (leftValue < rightValue) {
      return -1 * direction;
    }
    if (leftValue > rightValue) {
      return 1 * direction;
    }
    return 0;
  });
}

function mergeAndEvict(
  existing: AlertDto[],
  incoming: AlertDto[],
  evictedFingerprints: string[]
): AlertDto[] {
  const evicted = new Set(evictedFingerprints);
  const merged = new Map(
    existing
      .filter((alert) => !evicted.has(alert.fingerprint))
      .map((alert) => [alert.fingerprint, alert])
  );

  for (const alert of incoming) {
    merged.set(alert.fingerprint, alert);
  }

  return Array.from(merged.values());
}

export const useAlertsTableData = (query: AlertsTableDataQuery | undefined) => {
  const api = useApi();
  const { useLastAlerts } = useAlerts();
  const [shouldRefreshDate, setShouldRefreshDate] = useState<boolean>(false);

  const [canRevalidate, setCanRevalidate] = useState<boolean>(false);
  const [dateRangeCel, setDateRangeCel] = useState<string | null>(null);
  const [isPolling, setIsPolling] = useState<boolean>(false);
  const [alertsQueryState, setAlertsQueryState] = useState<
    AlertsQuery | undefined
  >(undefined);
  const incidentsQueryStateRef = useRef(alertsQueryState);
  const [facetsPanelRefreshToken, setFacetsPanelRefreshToken] = useState<
    string | undefined
  >(undefined);
  incidentsQueryStateRef.current = alertsQueryState;
  const isDateRangeInit = useRef(false);

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

  function updateAlertsCelDateRange() {
    if (!query?.timeFrame) {
      return;
    }

    const dateRangeCel = getDateRangeCel(query.timeFrame);

    setDateRangeCel(dateRangeCel);

    if (dateRangeCel) {
      return;
    }

    // if date does not change, just reload the data
    if (isDateRangeInit.current) {
      setFacetsPanelRefreshToken(uuidv4());
    }
    isDateRangeInit.current = true;
    mutateAlerts();
  }

  useEffect(() => updateAlertsCelDateRange(), [query?.timeFrame]);

  const { data: alertsChangeToken, fingerprints: polledFingerprints } =
    useAlertPolling(!isPaused);

  const [alertsToReturn, setAlertsToReturn] = useState<
    AlertDto[] | undefined
  >();
  const alertsToReturnRef = useRef(alertsToReturn);
  alertsToReturnRef.current = alertsToReturn;

  const patchVisibleAlerts = useCallback(
    async (
      fingerprints: string[],
      visibleAlerts: AlertDto[],
      sortOptions?: AlertsTableDataQuery["sortOptions"]
    ) => {
      if (!api.isReady() || fingerprints.length === 0 || visibleAlerts.length === 0) {
        return;
      }

      try {
        const batchAlerts = (await api.post(
          "/alerts/batch",
          fingerprints
        )) as AlertDto[];
        const updates = batchAlerts.map((alert) => ({
          ...alert,
          lastReceived: toDateObjectWithFallback(alert.lastReceived),
        }));

        const returnedFingerprints = new Set(
          updates.map((alert) => alert.fingerprint)
        );
        const evicted = fingerprints.filter(
          (fingerprint) => !returnedFingerprints.has(fingerprint)
        );

        setAlertsToReturn((current) =>
          sortAlerts(
            mergeAndEvict(current ?? visibleAlerts, updates, evicted),
            sortOptions
          )
        );
        setFacetsPanelRefreshToken(uuidv4());
      } catch {
        setShouldRefreshDate(true);
      }
    },
    [api]
  );

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
    if (!query || dateRangeCel === null) {
      return null;
    }

    const filterArray = [query?.searchCel, dateRangeCel];
    return filterArray
      .filter(Boolean)
      .map((cel) => `(${cel})`)
      .join(" && ");
  }, [query?.searchCel, dateRangeCel]);

  useEffect(() => {
    if (!query || mainCelQuery === null) {
      setAlertsQueryState(undefined);
      return;
    }

    const filterCel = query.filterCel ? `(${query.filterCel})` : "";
    const alertsQuery: AlertsQuery = {
      limit: query.limit,
      offset: query.offset,
      sortOptions: query.sortOptions,
      cel: [mainCelQuery, filterCel].filter(Boolean).join(" && "),
    };

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

  useEffect(() => {
    // When refresh token comes, this code allows polling for certain time and then stops.
    // Will start polling again when new refresh token comes.
    // Why? Because events are throttled on BE side but we want to refresh the data frequently
    // when keep gets ingested with data, and it requires control when to refresh from the UI side.
    if (!alertsChangeToken) {
      return;
    }

    if (polledFingerprints.length > 0 && !isPaused) {
      const visibleAlerts = alertsToReturnRef.current ?? alerts;
      const visibleFingerprints = new Set(
        (visibleAlerts ?? []).map((alert) => alert.fingerprint)
      );
      const allVisible = polledFingerprints.every((fingerprint) =>
        visibleFingerprints.has(fingerprint)
      );

      if (allVisible && visibleAlerts?.length) {
        void patchVisibleAlerts(
          polledFingerprints,
          visibleAlerts,
          query?.sortOptions
        );
        return;
      }
    }

    setShouldRefreshDate(true);
    const timeout = setTimeout(() => {
      setShouldRefreshDate(false);
    }, 15000);
    return () => clearTimeout(timeout);
  }, [
    alertsChangeToken,
    polledFingerprints,
    isPaused,
    alerts,
    patchVisibleAlerts,
    query?.sortOptions,
  ]);

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
