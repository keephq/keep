import { StoreApi } from "zustand";
import {
  createFacetsPanelStore,
  FacetsPanelState,
} from "../create-facets-store";
import { FacetDto } from "@/features/filter/models";

describe("useInitialStateHandler", () => {
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

  it("should toggle a facet option correctly", () => {
    const toggleFacetOption = store.getState().toggleFacetOption;

    // Initial state
    expect(store.getState().facetsState).toEqual({});
    expect(store.getState().facetsState["severityFacet"]).toBeFalsy();

    // Toggle an option off
    toggleFacetOption("severityFacet", "critical");
    expect(store.getState().facetsState["severityFacet"]).toEqual({
      "'high'": true,
      "'info'": true,
      "'low'": true,
      "'warning'": true,
    });

    // Toggle another option off
    toggleFacetOption("severityFacet", "high");
    expect(store.getState().facetsState["severityFacet"]).toEqual({
      "'info'": true,
      "'low'": true,
      "'warning'": true,
    });

    // Toggle an option on
    toggleFacetOption("severityFacet", "critical");
    expect(store.getState().facetsState["severityFacet"]).toEqual({
      "'critical'": true,
      "'info'": true,
      "'low'": true,
      "'warning'": true,
    });
  });

  it("should select one facet option correctly", () => {
    const selectOneFacetOption = store.getState().selectOneFacetOption;

    // Initial state
    expect(store.getState().facetsState).toEqual({});
    expect(store.getState().facetsState["severityFacet"]).toBeFalsy();

    // Select an option
    selectOneFacetOption("severityFacet", "critical");
    expect(store.getState().facetsState["severityFacet"]).toEqual({
      "'critical'": true,
    });

    // Select another option
    selectOneFacetOption("severityFacet", "high");
    expect(store.getState().facetsState["severityFacet"]).toEqual({
      "'high'": true,
    });
  });

  it("should select all facet options correctly", () => {
    const selectAllFacetOptions = store.getState().selectAllFacetOptions;

    // Initial state
    expect(store.getState().facetsState).toEqual({});
    expect(store.getState().facetsState["severityFacet"]).toBeFalsy();

    // Select all options
    selectAllFacetOptions("severityFacet");
    expect(store.getState().facetsState["severityFacet"]).toEqual({
      "'critical'": true,
      "'high'": true,
      "'info'": true,
      "'low'": true,
      "'warning'": true,
    });
  });
});
