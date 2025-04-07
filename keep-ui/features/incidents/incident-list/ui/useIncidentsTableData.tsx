import { TimeFrame } from "@/components/ui/DateRangePicker";
import {
  DEFAULT_INCIDENTS_CEL,
  DEFAULT_INCIDENTS_PAGE_SIZE,
  DEFAULT_INCIDENTS_SORTING,
  IncidentDto,
  PaginatedIncidentsDto,
} from "@/entities/incidents/model/models";
import { useIncidents, usePollIncidents } from "@/utils/hooks/useIncidents";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

export interface IncidentsTableDataQuery {
  candidate: boolean | null;
  predicted: boolean | null;
  limit: number;
  offset: number;
  sorting: { id: string; desc: boolean };
  filterCel: string;
  timeFrame: TimeFrame;
}

export const useIncidentsTableData = (
  initialData: PaginatedIncidentsDto | undefined,
  query: IncidentsTableDataQuery
) => {
  const [shouldRefreshDate, setShouldRefreshDate] = useState<boolean>(false);
  const [isPaused, setIsPaused] = useState<boolean>(true);
  const [timeframeDelta, setTimeframeDelta] = useState<number>(0);
  const [canRevalidate, setCanRevalidate] = useState<boolean>(false);
  const [dateRangeCel, setDateRangeCel] = useState<string | null>("");
  const [facetsDateRangeCel, setFacetsDateRangeCel] = useState<string | null>(
    ""
  );
  const [isPolling, setIsPolling] = useState<boolean>(false);
  const incidentsQueryRef = useRef<{
    limit: number;
    offset: number;
    sorting: { id: string; desc: boolean };
    incidentsCelQuery: string;
  } | null>(null);

  function onLiveUpdateStateChange(isPaused: boolean) {}

  useEffect(() => {
    if (canRevalidate) {
      return;
    }

    const timeout = setTimeout(() => {
      setCanRevalidate(true);
    }, 3000);
    return () => clearTimeout(timeout);
  }, [canRevalidate]);

  const getDateRangeCel = useCallback(() => {
    const filterArray = [];
    const currentDate = new Date();

    if (timeframeDelta > 0) {
      filterArray.push(
        `creation_time >= '${new Date(
          currentDate.getTime() - timeframeDelta
        ).toISOString()}'`
      );
      filterArray.push(`creation_time <= '${currentDate.toISOString()}'`);
      return filterArray.join(" && ");
    }

    return null;
  }, [timeframeDelta]);

  function updateAlertsCelDateRange() {
    // if (!canRevalidate) {
    //   return;
    // }

    const dateRangeCel = getDateRangeCel();
    setIsPolling(true);

    setDateRangeCel(dateRangeCel);

    if (dateRangeCel) {
      return;
    }

    // if date does not change, just reload the data
    mutateIncidents();
    // onReload && onReload(incidentsQueryRef.current);
  }

  useEffect(() => updateAlertsCelDateRange(), [timeframeDelta]);

  const { incidentChangeToken } = usePollIncidents(() => {}, isPaused);

  useEffect(() => {
    if (query.timeFrame?.paused != isPaused) {
      onLiveUpdateStateChange &&
        onLiveUpdateStateChange(!query.timeFrame?.paused);
    }

    const newDiff =
      (query.timeFrame?.end?.getTime() || 0) -
      (query.timeFrame?.start?.getTime() || 0);
    setTimeframeDelta(newDiff);
    setIsPaused(!!query.timeFrame?.paused);
  }, [
    query.timeFrame,
    setIsPaused,
    onLiveUpdateStateChange,
    setTimeframeDelta,
  ]);

  useEffect(() => {
    console.log("IHOR TOKEN CHANGE");
    // When refresh token comes, this code allows polling for certain time and then stops.
    // Will start polling again when new refresh token comes.
    // Why? Because events are throttled on BE side but we want to refresh the data frequently
    // when keep gets ingested with data, and it requires control when to refresh from the UI side.
    if (incidentChangeToken) {
      setShouldRefreshDate(true);
      const timeout = setTimeout(() => {
        setShouldRefreshDate(false);
      }, 15000);
      return () => clearTimeout(timeout);
    }
  }, [incidentChangeToken]);

  useEffect(() => {
    // so that gap between poll is 2x of query time and minimum 3sec
    const refreshInterval = Math.max((responseTimeMs || 1000) * 2, 3000);
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
    incidentsQueryRef.current = {
      limit: query.limit,
      offset: query.offset,
      sorting: query.sorting,
      incidentsCelQuery: [mainCelQuery, query.filterCel]
        .filter(Boolean)
        .join(" && "),
    };
  }, [query.sorting, query.filterCel, query.limit, query.offset, mainCelQuery]);

  const {
    data: incidents,
    isLoading: incidentsLoading,
    mutate: mutateIncidents,
    error: incidentsError,
    responseTimeMs,
  } = useIncidents(
    null,
    null,
    incidentsQueryRef.current?.limit,
    incidentsQueryRef.current?.offset,
    incidentsQueryRef.current?.sorting,
    incidentsQueryRef.current?.incidentsCelQuery,
    {
      revalidateOnFocus: false,
      revalidateOnMount: !initialData,
      fallbackData: initialData,
      onSuccess: () => {
        refreshDefaultIncidents();
      },
    }
  );

  const { data: defaultIncidents, mutate: refreshDefaultIncidents } =
    useIncidents(
      null,
      null,
      DEFAULT_INCIDENTS_PAGE_SIZE,
      0,
      DEFAULT_INCIDENTS_SORTING,
      DEFAULT_INCIDENTS_CEL,
      {
        revalidateOnFocus: false,
        revalidateOnMount: false,
        fallbackData: initialData,
      }
    );

  const { data: predictedIncidents, isLoading: isPredictedLoading } =
    useIncidents(true, true);

  return {
    incidents,
    incidentsLoading: !isPolling && incidentsLoading,
    defaultIncidents,
    predictedIncidents,
    isPredictedLoading,
    facetsCel: mainCelQuery,
    incidentChangeToken,
    incidentsError,
  };
};
