import { renderHook, act } from "@testing-library/react";
import {
  useAlertsTableData,
  AlertsTableDataQuery,
} from "../useAlertsTableData";
import { AlertsQuery, useAlerts } from "@/entities/alerts/model";
import { useAlertPolling } from "@/utils/hooks/useAlertPolling";
import {
  AbsoluteTimeFrame,
  AllTimeFrame,
} from "@/components/ui/DateRangePickerV2";

jest.useFakeTimers();
jest.mock("@/entities/alerts/model", () => ({
  useAlerts: jest.fn(),
}));
jest.mock("@/utils/hooks/useAlertPolling", () => ({
  useAlertPolling: jest.fn(),
}));
jest.mock("uuid", () => ({ v4: () => "mock-uuid" }));

const mockUseLastAlerts = jest.fn();
(useAlerts as jest.Mock).mockReturnValue({ useLastAlerts: mockUseLastAlerts });

const mockMutate = jest.fn();

const defaultAlerts = [{ id: 1, name: "Alert 1" }];
const defaultQuery: AlertsTableDataQuery = {
  searchCel: "test",
  filterCel: "filter",
  limit: 10,
  offset: 0,
  sortOptions: [{ sortBy: "name", sortDirection: "ASC" }],
  timeFrame: { type: "relative", deltaMs: 60000, isPaused: false },
};

beforeEach(() => {
  jest.clearAllMocks();
  mockUseLastAlerts.mockReturnValue({
    data: defaultAlerts,
    totalCount: 1,
    isLoading: false,
    mutate: mockMutate,
    error: null,
    queryTimeInSeconds: 1,
  });
  (useAlertPolling as jest.Mock).mockReturnValue({ data: null });
});

describe("useAlertsTableData", () => {
  it("returns alerts and related data", () => {
    const { result } = renderHook(() => useAlertsTableData(defaultQuery));
    expect(result.current.alerts).toEqual(defaultAlerts);
    expect(result.current.totalCount).toBe(1);
    expect(result.current.alertsLoading).toBe(false);
    expect(result.current.facetsCel).toContain("test");
    expect(result.current.alertsError).toBeNull();
    expect(typeof result.current.mutateAlerts).toBe("function");
  });

  it("handles undefined query", () => {
    const { result } = renderHook(() => useAlertsTableData(undefined));
    expect(mockUseLastAlerts).toHaveBeenCalledWith(undefined, {
      revalidateOnFocus: false,
      revalidateOnMount: true,
    });
  });

  it("handles error state", () => {
    mockUseLastAlerts.mockReturnValue({
      data: undefined,
      totalCount: 0,
      isLoading: false,
      mutate: mockMutate,
      error: new Error("Test error"),
      queryTimeInSeconds: 1,
    });
    const { result } = renderHook(() => useAlertsTableData(defaultQuery));
    expect(result.current.alertsError).toBeInstanceOf(Error);
  });

  it("updates alerts when polling token changes", () => {
    (useAlertPolling as jest.Mock).mockReturnValue({ data: "token" });
    const { result } = renderHook(() => useAlertsTableData(defaultQuery));
    expect(result.current.alertsChangeToken).toBe("token");
  });

  it("generates correct facetsCel for absolute timeFrame", () => {
    const { result } = renderHook(() =>
      useAlertsTableData({
        ...defaultQuery,
        searchCel: "name == 'foo'",
        filterCel: "description in ['bar', 'baz']",
        timeFrame: {
          type: "absolute",
          start: new Date(0),
          end: new Date(1000),
          isPaused: false,
        } as AbsoluteTimeFrame,
      })
    );
    expect(result.current.facetsCel).toBe(
      "(name == 'foo') && (lastReceived >= '1970-01-01T00:00:00.000Z' && lastReceived <= '1970-01-01T00:00:01.000Z')"
    );
  });

  it("calls useLastAlerts with correct query", () => {
    const query: AlertsTableDataQuery = {
      searchCel: "name == 'foo'",
      filterCel: "(description in ['bar', 'baz'])",
      limit: 10,
      offset: 200,
      sortOptions: [{ sortBy: "name", sortDirection: "ASC" }],
      timeFrame: {
        type: "absolute",
        start: new Date(0),
        end: new Date(1000),
        isPaused: false,
      } as AbsoluteTimeFrame,
    };
    const { result } = renderHook(() => useAlertsTableData(query));
    expect(mockUseLastAlerts).toHaveBeenCalledWith(
      {
        cel: "(name == 'foo') && (lastReceived >= '1970-01-01T00:00:00.000Z' && lastReceived <= '1970-01-01T00:00:01.000Z') && (description in ['bar', 'baz'])",
        limit: 10,
        offset: 200,
        sortOptions: [{ sortBy: "name", sortDirection: "ASC" }],
      } as AlertsQuery,
      { revalidateOnFocus: false, revalidateOnMount: true }
    );
  });

  it("handles paused state", () => {
    const pausedQuery = {
      ...defaultQuery,
      timeFrame: { ...defaultQuery.timeFrame, isPaused: true },
    };
    const { result } = renderHook(() => useAlertsTableData(pausedQuery));
    expect(result.current.alerts).toEqual(defaultAlerts);
  });

  it("provides facetsPanelRefreshToken when timeframe changes to AllTimeFrame", () => {
    const query: AlertsTableDataQuery = {
      ...defaultQuery,
      timeFrame: { type: "relative", deltaMs: 60000, isPaused: false },
    };
    const { result, rerender } = renderHook(
      ({ query }) => useAlertsTableData(query),
      {
        initialProps: { query },
      }
    );

    act(() => {
      jest.advanceTimersByTime(200); // Simulate time passing
    });

    rerender({
      query: {
        ...query,
        timeFrame: {
          type: "all-time",
          isPaused: false,
        } as AllTimeFrame,
      },
    });
    expect(result.current.facetsPanelRefreshToken).toBe(undefined); // should be still undefined
    rerender({
      query: {
        ...query,
        timeFrame: {
          type: "all-time",
          isPaused: false,
        } as AllTimeFrame,
      },
    });

    expect(result.current.facetsPanelRefreshToken).toBe("mock-uuid");
  });

  // Additional tests

  it("returns null facetsCel if query or dateRangeCel is null", () => {
    const { result } = renderHook(() => useAlertsTableData(undefined));
    expect(result.current.facetsCel).toBeNull();
  });

  it("calls mutateAlerts when mutateAlerts is invoked", () => {
    const { result } = renderHook(() => useAlertsTableData(defaultQuery));
    act(() => {
      result.current.mutateAlerts();
    });
    expect(mockMutate).toHaveBeenCalled();
  });

  it("returns alerts if isPaused and alertsLoading is false", () => {
    mockUseLastAlerts.mockReturnValueOnce({
      data: defaultAlerts,
      totalCount: 1,
      isLoading: false,
      mutate: mockMutate,
      error: null,
      queryTimeInSeconds: 1,
    });
    const pausedQuery = {
      ...defaultQuery,
      timeFrame: { ...defaultQuery.timeFrame, isPaused: true },
    };
    const { result } = renderHook(() => useAlertsTableData(pausedQuery));
    expect(result.current.alerts).toEqual(defaultAlerts);
  });

  it("alertsLoading is false when isLoading is true and polling is triggered", () => {
    mockUseLastAlerts.mockReturnValueOnce({
      data: defaultAlerts,
      totalCount: 1,
      isLoading: true,
      mutate: mockMutate,
      error: null,
      queryTimeInSeconds: 1,
    });
    (useAlertPolling as jest.Mock).mockReturnValueOnce({
      data: "polling-token",
    });
    const { result } = renderHook(() => useAlertsTableData(defaultQuery));

    act(() => {
      jest.advanceTimersByTime(1000); // Simulate time passing for polling
    });

    // isPolling is set to false after mount, so alertsLoading should be true
    expect(result.current.alertsLoading).toBe(false);
  });

  it("alertsLoading is true when isLoading is true and polling has expired", () => {
    mockUseLastAlerts.mockReturnValue({
      data: defaultAlerts,
      totalCount: 1,
      isLoading: true,
      mutate: mockMutate,
      error: null,
      queryTimeInSeconds: 1,
    });
    (useAlertPolling as jest.Mock).mockReturnValue({ data: "polling-token" });
    const { result, rerender } = renderHook(
      ({ query }) => useAlertsTableData(query),
      {
        initialProps: { query: defaultQuery },
      }
    );

    act(() => {
      jest.advanceTimersByTime(16000); // Simulate time passing for polling
    });

    rerender({
      query: {
        ...defaultQuery,
        searchCel: "foo",
      },
    }); // trigger query change

    expect(result.current.alertsLoading).toBe(true);
  });

  it("returns correct facetsCel with only searchCel", () => {
    const { result } = renderHook(() =>
      useAlertsTableData({
        ...defaultQuery,
        timeFrame: {
            type: "all-time",
            isPaused: false,
        } as AllTimeFrame,
        searchCel: "name == 'foo'",
        filterCel: "",
      })
    );
    expect(result.current.facetsCel).toBe("(name == 'foo')");
  });

  it("returns correct facetsCel with only dateRangeCel", () => {
    const { result } = renderHook(() =>
      useAlertsTableData({
        ...defaultQuery,
        timeFrame: {
          type: "absolute",
          start: new Date("2025-07-02T10:28:27.289Z"),
          end: new Date("2025-07-02T10:29:24.640Z"),
          isPaused: false,
        } as AbsoluteTimeFrame,
        searchCel: "",
        filterCel: "",
      })
    );
    expect(result.current.facetsCel).toBe(
      "(lastReceived >= '2025-07-02T10:28:27.289Z' && lastReceived <= '2025-07-02T10:29:24.640Z')"
    );
  });

  it("returns correct facetsCel with both searchCel and dateRangeCel", () => {
    const { result } = renderHook(() =>
      useAlertsTableData({
        ...defaultQuery,
        timeFrame: {
          type: "absolute",
          start: new Date("2025-07-02T10:28:27.289Z"),
          end: new Date("2025-07-02T10:29:24.640Z"),
          isPaused: false,
        } as AbsoluteTimeFrame,
        searchCel: "name == 'foo'",
        filterCel: "description in ['bar', 'baz']",
      })
    );
    expect(result.current.facetsCel).toContain(
      "(name == 'foo') && (lastReceived >= '2025-07-02T10:28:27.289Z' && lastReceived <= '2025-07-02T10:29:24.640Z')"
    );
  });
});
