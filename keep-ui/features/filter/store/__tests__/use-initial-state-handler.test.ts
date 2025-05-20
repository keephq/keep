import { useInitialStateHandler } from "../use-initial-state-handler";

import { StoreApi } from "zustand";
import { renderHook } from "@testing-library/react";
import {
  createFacetsPanelStore,
  FacetsPanelState,
} from "../create-facets-store";
import { FacetConfig, FacetDto, FacetsConfig } from "@/features/filter/models";
import { useFacetsConfig } from "../use-facets-config";

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
      facetOptions: null,
      facetsState: {},
      isInitialStateHandled: false,
    });
    const facetsConfig: FacetsConfig = {
      Status: {
        checkedByDefaultOptionValues: ["firing", "acknowledged"],
      } as FacetConfig,
    };

    renderHook(() => useFacetsConfig(facetsConfig, store));
    renderHook(() => useInitialStateHandler(store));
  });

  it("should set default option values for status facet", () => {
    expect(store.getState().facetsState).toEqual(
      expect.objectContaining({
        statusFacet: {
          "'firing'": true,
          "'acknowledged'": true,
        },
      })
    );
  });

  it("should set default option values for status facet", () => {
    expect(store.getState().facetsState).not.toEqual(
      expect.objectContaining({
        severityFacet: expect.anything(),
      })
    );
  });
});
