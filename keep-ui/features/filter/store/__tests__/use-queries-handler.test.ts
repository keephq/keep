import { StoreApi } from "zustand";
import { renderHook, act } from "@testing-library/react";
import { useQueriesHandler } from "../use-queries-handler";
import {
  createFacetsPanelStore,
  FacetsPanelState,
} from "../create-facets-store";
import { FacetDto } from "@/features/filter/models";
jest.useFakeTimers();

describe("useQueriesHandler", () => {
  let store: StoreApi<FacetsPanelState>;

  beforeEach(() => {
    store = createFacetsPanelStore();
    store.setState({
      facets: [
        {
          id: "severityFacet",
          name: "Severity",
          property_path: "severity",
        } as FacetDto,
        {
          id: "incidentNameFacet",
          name: "Incident name",
          property_path: "incident.name",
        } as FacetDto,
        {
          id: "statusFacet",
          name: "Status",
          property_path: "status",
        } as FacetDto,
      ],
      facetOptions: {
        severityFacet: [
          {
            display_name: "Critical",
            value: "critical",
            matches_count: 12,
          },
          { display_name: "High", value: "high", matches_count: 3 },
          { display_name: "Warning", value: "warning", matches_count: 4 },
          { display_name: "Info", value: "info", matches_count: 21 },
          { display_name: "Low", value: "low", matches_count: 9 },
        ],
        incidentNameFacet: [
          {
            display_name: "HTTP 500 error, needs clarification",
            value: "HTTP 500 error, needs clarification",
            matches_count: 12,
          },
          {
            display_name: "Error processing event 'datadog'",
            value: "Error processing event 'datadog'",
            matches_count: 3,
          },
          {
            display_name: "Error processing event 'aws'",
            value: "Error processing event 'aws'",
            matches_count: 4,
          },
        ],
        statusFacet: [
          {
            display_name: "Firing",
            value: "firing",
            matches_count: 1,
          },
          {
            display_name: "Suppressed",
            value: "suppressed",
            matches_count: 10,
          },
          { display_name: "Resolved", value: "resolved", matches_count: 43 },
        ],
      },
      facetsState: {},
      isFacetsStateInitializedFromQueryParams: false,
      isInitialStateHandled: true,
    });
  });

  it("should not update queries state when facets state is empty", () => {
    const { result } = renderHook(() => useQueriesHandler(store));

    expect(store.getState().queriesState).toEqual({
      facetOptionQueries: null,
      filterCel: null,
    });
  });

  it("should update queries state when facets state changes", () => {
    renderHook(() => useQueriesHandler(store));

    act(() => {
      store.setState({
        facetsState: {
          severityFacet: { critical: true, high: true },
          statusFacet: { firing: true },
        },
        facetsStateRefreshToken: "some-token",
        isFacetsStateInitializedFromQueryParams: true,
      });
    });

    act(() => {
      jest.advanceTimersByTime(200);
    });

    expect(store.getState().queriesState).toEqual({
      filterCel: "(severity in [critical, high]) && (status in [firing])",
      facetOptionQueries: {
        severityFacet: "(status in [firing])",
        statusFacet: "(severity in [critical, high])",
        incidentNameFacet:
          "(severity in [critical, high]) && (status in [firing])",
      },
    });
  });

  it("should not include facets with all options selected in filterCel", () => {
    renderHook(() => useQueriesHandler(store));

    act(() => {
      store.setState({
        facetsState: {
          severityFacet: {
            critical: true,
            high: true,
            warning: true,
            info: true,
            low: true,
          },
          statusFacet: { firing: true },
        },
        facetsStateRefreshToken: "some-token",
        isFacetsStateInitializedFromQueryParams: true,
      });
    });

    act(() => {
      jest.advanceTimersByTime(200);
    });

    expect(store.getState().queriesState).toEqual({
      filterCel: "(status in [firing])",
      facetOptionQueries: {
        severityFacet: "(status in [firing])",
        statusFacet: "",
        incidentNameFacet: "(status in [firing])",
      },
    });
  });

  it("should not update queries state when isFacetsStateInitializedFromQueryParams is false", () => {
    renderHook(() => useQueriesHandler(store));

    act(() => {
      store.setState({
        facetsState: {
          severityFacet: { critical: true, high: true },
          statusFacet: { firing: true },
        },
        facetsStateRefreshToken: "some-token",
        isFacetsStateInitializedFromQueryParams: false,
      });
    });
    act(() => {
      jest.advanceTimersByTime(200);
    });
    expect(store.getState().queriesState).toEqual({
      facetOptionQueries: null,
      filterCel: null,
    });
  });

  it("should handle complex facet paths correctly", () => {
    renderHook(() => useQueriesHandler(store));

    act(() => {
      store.setState({
        facetsState: {
          incidentNameFacet: {
            "'HTTP 500 error, needs clarification'": true,
            "'Error processing event \\'datadog\\''": true,
          },
        },
        facetsStateRefreshToken: "some-token",
        isFacetsStateInitializedFromQueryParams: true,
      });
    });
    act(() => {
      jest.advanceTimersByTime(200);
    });
    expect(store.getState().queriesState).toEqual({
      filterCel:
        "(incident.name in ['HTTP 500 error, needs clarification', 'Error processing event \\'datadog\\''])",
      facetOptionQueries: {
        severityFacet:
          "(incident.name in ['HTTP 500 error, needs clarification', 'Error processing event \\'datadog\\''])",
        statusFacet:
          "(incident.name in ['HTTP 500 error, needs clarification', 'Error processing event \\'datadog\\''])",
        incidentNameFacet: "",
      },
    });
  });
});
