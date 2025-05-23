import { useQueryParams } from "../use-query-params";
import { StoreApi } from "zustand";
import {
  createFacetsPanelStore,
  FacetsPanelState,
} from "../../create-facets-store";
import { FacetDto } from "@/features/filter/models";
import { renderHook, act } from "@testing-library/react";
import { useSearchParams } from "next/navigation";

jest.mock("next/navigation", () => ({
  useSearchParams: jest.fn(),
  usePathname: jest.fn(() => "/alerts/feed"),
}));
jest.useFakeTimers();

describe("useQueryParams", () => {
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

  it("should initialize facets state from query params only one time", () => {
    (useSearchParams as jest.Mock).mockReturnValue(
      new URLSearchParams({
        facet_severity: "'critical','high'",
        facet_incident_name: "'HTTP 500 error, needs clarification'",
      })
    );

    renderHook(() => useQueryParams(store));

    expect(store.getState().facetsState).toEqual({
      severityFacet: { "'critical'": true, "'high'": true },
      incidentNameFacet: {
        "'HTTP 500 error, needs clarification'": true,
      },
    });
    expect(store.getState().isFacetsStateInitializedFromQueryParams).toBe(true);

    // mock new query params
    (useSearchParams as jest.Mock).mockReturnValue(
      new URLSearchParams({
        facet_severity: "'critical'",
        facet_incident_name: "'Error processing event 'datadog''",
      })
    );

    renderHook(() => useQueryParams(store));

    // simulate facet change in state
    act(() =>
      store.getState().setFacets([...(store.getState().facets as FacetDto[])])
    );

    expect(store.getState().facetsState).toEqual({
      severityFacet: { "'critical'": true, "'high'": true },
      incidentNameFacet: {
        "'HTTP 500 error, needs clarification'": true,
      },
    });
  });

  it("should do nothing if query params are set", () => {
    (useSearchParams as jest.Mock).mockReturnValue(
      new URLSearchParams({
        facet_severity: "'critical','high'",
        facet_incident_name: "'HTTP 500 error, needs clarification'",
      })
    );
    act(() =>
      store.getState().setIsFacetsStateInitializedFromQueryParams(true)
    );
    renderHook(() => useQueryParams(store));

    // simulate facet change in state
    expect(store.getState().facetsState).toEqual({});
  });

  it("should update query params when facets state changes", () => {
    (useSearchParams as jest.Mock).mockReturnValue(new URLSearchParams());

    renderHook(() => useQueryParams(store));

    act(() => {
      store.setState({
        facetsState: {
          severityFacet: { "'critical'": true, "'high'": true },
          incidentNameFacet: {
            "'HTTP 500 error\\, needs clarification'": true,
            "'Error processing event \\'datadog\\''": true,
          },
        },
      });
    });

    act(() => {
      // 600 is used to perform check after 500 debounce time
      jest.advanceTimersByTime(600);
    });

    const searchEntries = Array.from(
      new URLSearchParams(window.location.search).entries()
    );

    expect(searchEntries).toHaveLength(2);

    expect(searchEntries).toContainEqual([
      "facet_incident_name",
      "'HTTP 500 error\\, needs clarification','Error processing event \\'datadog\\''",
    ]);
    expect(searchEntries).toContainEqual([
      "facet_severity",
      "'critical','high'",
    ]);
  });

  it("should update query params when facets state changes skipping facets whose all options are selected", () => {
    (useSearchParams as jest.Mock).mockReturnValue(new URLSearchParams());

    renderHook(() => useQueryParams(store));

    act(() => {
      store.setState({
        facetsState: {
          severityFacet: { "'critical'": true, "'high'": true },
          statusFacet: {
            "'firing'": true,
            "'resolved'": true,
            "'suppressed'": true,
          },
        },
      });
    });

    act(() => {
      // 600 is used to perform check after 500 debounce time
      jest.advanceTimersByTime(600);
    });

    const searchEntries = Array.from(
      new URLSearchParams(window.location.search).entries()
    );

    expect(searchEntries).toHaveLength(1);
    expect(searchEntries).toContainEqual([
      "facet_severity",
      "'critical','high'",
    ]);
  });

  describe("when unmounting", () => {
    it("should clean up only facet-related query params when path changes", () => {
      (useSearchParams as jest.Mock).mockReturnValue(
        new URLSearchParams({
          facet_severity: "'critical','high'",
          facet_incident_name: "'HTTP 500 error, needs clarification'",
          unrelated_param: "some_value",
        })
      );

      const { unmount } = renderHook(() => useQueryParams(store));

      // Simulate path change
      (
        jest.requireMock("next/navigation").usePathname as jest.Mock
      ).mockReturnValue("/alerts/details");
      act(() => {
        unmount();
      });

      const searchEntries = Array.from(
        new URLSearchParams(window.location.search).entries()
      );

      expect(searchEntries).toHaveLength(1);
      expect(searchEntries).toContainEqual(["unrelated_param", "some_value"]);
    });
  });
});
