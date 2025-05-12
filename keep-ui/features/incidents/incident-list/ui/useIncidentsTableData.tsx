import { TimeFrame } from "@/components/ui/DateRangePicker";
import { TimeFrameV2 } from "@/components/ui/DateRangePickerV2";
import {
  DEFAULT_INCIDENTS_CEL,
  DEFAULT_INCIDENTS_PAGE_SIZE,
  DEFAULT_INCIDENTS_SORTING,
  PaginatedIncidentsDto,
} from "@/entities/incidents/model/models";
import {
  IncidentsQuery,
  useIncidents,
  usePollIncidents,
} from "@/utils/hooks/useIncidents";
import { useEffect, useMemo, useRef, useState } from "react";

export interface IncidentsTableDataQuery {
  candidate: boolean | null;
  predicted: boolean | null;
  limit: number;
  offset: number;
  sorting: { id: string; desc: boolean };
  filterCel: string;
  timeFrame: TimeFrameV2;
}

export const useIncidentsTableData = (
  initialData: PaginatedIncidentsDto | undefined,
  query: IncidentsTableDataQuery
) => {
  const [shouldRefreshDate, setShouldRefreshDate] = useState<boolean>(false);
  const [canRevalidate, setCanRevalidate] = useState<boolean>(false);
  const [dateRangeCel, setDateRangeCel] = useState<string | null>("");
  const [isPolling, setIsPolling] = useState<boolean>(false);
  const [incidentsQueryState, setIncidentsQueryState] =
    useState<IncidentsQuery | null>(null);
  const incidentsQueryStateRef = useRef(incidentsQueryState);
  incidentsQueryStateRef.current = incidentsQueryState;

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
      return `creation_time >= '${new Date(
        new Date().getTime() - query.timeFrame.deltaMs
      ).toISOString()}'`;
    } else if (query?.timeFrame.type === "absolute") {
      return [
        `creation_time >= '${query.timeFrame.start.toISOString()}'`,
        `creation_time <= '${query.timeFrame.end.toISOString()}'`,
      ].join(" && ");
    }

    return null;
  };

  function updateIncidentsCelDateRange() {
    const dateRangeCel = getDateRangeCel();
    setIsPolling(true);

    setDateRangeCel(dateRangeCel);

    if (dateRangeCel) {
      return;
    }

    // if date does not change, just reload the data
    mutateIncidents();
  }

  useEffect(() => updateIncidentsCelDateRange(), [query.timeFrame]);

  const { incidentChangeToken } = usePollIncidents(() => {}, isPaused);

  useEffect(() => {
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
    if (isPaused) {
      return;
    }
    // so that gap between poll is 2x of query time and minimum 3sec
    const refreshInterval = Math.max((responseTimeMs || 1000) * 2, 6000);
    const interval = setInterval(() => {
      if (!isPaused && shouldRefreshDate) {
        updateIncidentsCelDateRange();
      }
    }, refreshInterval);
    return () => clearInterval(interval);
  }, [isPaused, shouldRefreshDate]);

  const mainCelQuery = useMemo(() => {
    const filterArray = ["is_candidate == false", dateRangeCel];

    return filterArray.filter(Boolean).join(" && ");
  }, [dateRangeCel]);

  useEffect(() => {
    setIncidentsQueryState({
      candidate: null,
      predicted: null,
      limit: query.limit,
      offset: query.offset,
      sorting: query.sorting,
      cel: [mainCelQuery, query.filterCel].filter(Boolean).join(" && "),
    });
  }, [query.sorting, query.filterCel, query.limit, query.offset, mainCelQuery]);

  const {
    data: paginatedIncidentsFromHook,
    isLoading: incidentsLoading,
    mutate: mutateIncidents,
    error: incidentsError,
    responseTimeMs,
  } = useIncidents(
    incidentsQueryState,
    {
      revalidateOnFocus: false,
      revalidateOnMount: !initialData,
      onSuccess: () => {
        refreshDefaultIncidents();
      },
    },
    true
  );

  const { data: defaultIncidents, mutate: refreshDefaultIncidents } =
    useIncidents(
      {
        candidate: null,
        predicted: null,
        limit: 0,
        offset: 0,
        sorting: DEFAULT_INCIDENTS_SORTING,
        cel: DEFAULT_INCIDENTS_CEL,
      },
      {
        revalidateOnFocus: false,
        revalidateOnMount: false,
        fallbackData: initialData,
      }
    );

  const { data: predictedIncidents, isLoading: isPredictedLoading } =
    useIncidents({ candidate: true, predicted: true });

  const [paginatedIncidentsToReturn, setPaginatedIncidentsToReturn] = useState<
    PaginatedIncidentsDto | undefined
  >(initialData);
  useEffect(() => {
    if (!paginatedIncidentsFromHook) {
      return;
    }

    if (!isPaused) {
      if (!incidentsLoading) {
        setPaginatedIncidentsToReturn(paginatedIncidentsFromHook);
      }

      return;
    }

    setPaginatedIncidentsToReturn(
      incidentsLoading ? undefined : paginatedIncidentsFromHook
    );
  }, [isPaused, incidentsLoading, paginatedIncidentsFromHook]);

  return {
    incidents: paginatedIncidentsToReturn,
    incidentsLoading: !isPolling && incidentsLoading,
    isEmptyState: defaultIncidents.count === 0,
    predictedIncidents,
    isPredictedLoading,
    facetsCel: mainCelQuery,
    incidentChangeToken,
    incidentsError,
  };
};
