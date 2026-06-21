import { createStore } from "zustand";
import { v4 as uuidV4 } from "uuid";
import { FacetDto, FacetOptionDto, FacetsConfig, FacetState } from "../models";
import { toFacetState, valueToString } from "./utils";

export type FacetsPanelState = {
  facetsConfig: FacetsConfig | null;
  setFacetsConfig: (facetsConfig: FacetsConfig) => void;

  facets: FacetDto[] | null;
  setFacets: (facets: FacetDto[]) => void;

  /**
   * IDs of facets whose options should be loaded. Non-lazy facets are active
   * immediately; lazy facets become active only once the user expands them or
   * they have selected options. This prevents loading options for every lazy
   * facet on mount, which froze the page with high facet cardinality (#6577).
   */
  activeFacetIds: Record<string, boolean>;
  setFacetActive: (facetId: string) => void;

  facetOptions: Record<string, FacetOptionDto[]> | null;
  setFacetOptions: (facetOptions: Record<string, FacetOptionDto[]>) => void;

  facetOptionsLoadingState: Record<string, string>;
  setFacetOptionsLoadingState: (loadingState: Record<string, string>) => void;

  queriesState: {
    facetOptionQueries: Record<string, string> | null;
    filterCel: string | null;
  };
  setQueriesState: (
    filterCel: string,
    facetOptionQueries: Record<string, string>
  ) => void;

  facetsState: FacetState;

  patchFacetsState: (facetsStatePatch: FacetState) => void;
  toggleFacetOption: (facetId: string, optionValue: string) => void;
  selectOneFacetOption: (facetId: string, optionValue: string) => void;
  selectAllFacetOptions: (facetId: string) => void;
  dirtyFacetIds: string[];

  facetsStateRefreshToken: string | null;

  isFacetsStateInitializedFromQueryParams: boolean;
  setIsFacetsStateInitializedFromQueryParams: (
    isFacetsStateInitializedFromQueryParams: boolean
  ) => void;

  isInitialStateHandled: boolean;
  setIsInitialStateHandled: (isInitialStateHandled: boolean) => void;

  clearFilters: () => void;

  changedFacetId: string | null;
  setChangedFacetId: (facetId: string | null) => void;

  areOptionsReLoading: boolean;
  setAreOptionsReLoading: (isLoading: boolean) => void;

  areOptionsLoading: boolean;
  setAreOptionsLoading: (isLoading: boolean) => void;
};

export const createFacetsPanelStore = () =>
  createStore<FacetsPanelState>((set, state) => ({
    facetsConfig: null,
    setFacetsConfig: (facetsConfig: FacetsConfig) => set({ facetsConfig }),

    facets: null,
    setFacets: (facets: FacetDto[]) => {
      const previousActive = state().activeFacetIds || {};
      const activeFacetIds: Record<string, boolean> = { ...previousActive };
      // Non-lazy facets are always active and load options eagerly.
      facets.forEach((facet) => {
        if (!facet.is_lazy) {
          activeFacetIds[facet.id] = true;
        }
      });
      set({ facets, activeFacetIds });
    },

    activeFacetIds: {},
    setFacetActive: (facetId: string) => {
      if (state().activeFacetIds?.[facetId]) {
        return;
      }
      set({
        activeFacetIds: { ...(state().activeFacetIds || {}), [facetId]: true },
      });
    },

    facetOptions: null,
    setFacetOptions: (facetOptions: Record<string, FacetOptionDto[]>) =>
      set({ facetOptions }),

    facetOptionsLoadingState: {},
    setFacetOptionsLoadingState: (loadingState: Record<string, string>) =>
      set({ facetOptionsLoadingState: loadingState }),

    queriesState: {
      facetOptionQueries: null,
      filterCel: null,
    },
    setQueriesState: (filterCel, facetOptionQueries) =>
      set({
        queriesState: {
          filterCel,
          facetOptionQueries,
        },
      }),

    dirtyFacetIds: [],

    facetsState: {},
    patchFacetsState: (facetsStatePatch) => {
      // Facets that have a (pre)selected state must load their options so the
      // selection can be reflected, even if they are lazy and collapsed.
      const activeFacetIds = { ...(state().activeFacetIds || {}) };
      Object.keys(facetsStatePatch).forEach((facetId) => {
        activeFacetIds[facetId] = true;
      });
      set({
        // So that it only triggers refresh when facetsState is patched once
        facetsStateRefreshToken: state().facetsStateRefreshToken || uuidV4(),
        activeFacetIds,
        facetsState: {
          ...(state().facetsState || {}),
          ...facetsStatePatch,
        },
      });
    },
    toggleFacetOption(facetId, optionValue) {
      const currentState = state();
      const facetsState = currentState.facetsState || {};
      const strValue = valueToString(optionValue);
      let newFacetState = {};

      if (!facetsState[facetId]) {
        newFacetState = toFacetState(
          currentState.facetOptions?.[facetId]
            .map((option) => valueToString(option.value))
            .filter((optionStrValue) => optionStrValue !== strValue) || []
        );
      } else {
        let selectedValues = Object.keys(facetsState[facetId]);

        if (strValue in facetsState[facetId]) {
          selectedValues = selectedValues.filter(
            (selectedValue) => selectedValue !== strValue
          );
        } else {
          selectedValues.push(strValue);
        }
        newFacetState = toFacetState(selectedValues);
      }

      set({
        // So that it only triggers refresh when facetsState is changed once (option is selected\deselected by user)
        facetsStateRefreshToken: uuidV4(),
        changedFacetId: facetId,
        activeFacetIds: { ...(state().activeFacetIds || {}), [facetId]: true },
        dirtyFacetIds: Array.from(new Set(state().dirtyFacetIds).add(facetId)),
        facetsState: {
          ...facetsState,
          [facetId]: newFacetState,
        },
      });
    },
    selectOneFacetOption(facetId, optionValue) {
      const currentState = state();
      const facetsState = currentState.facetsState || {};

      set({
        // So that it only triggers refresh when facetsState is changed once (option is selected\deselected by user)
        facetsStateRefreshToken: uuidV4(),
        changedFacetId: facetId,
        activeFacetIds: { ...(state().activeFacetIds || {}), [facetId]: true },
        dirtyFacetIds: Array.from(new Set(state().dirtyFacetIds).add(facetId)),
        facetsState: {
          ...facetsState,
          [facetId]: toFacetState([valueToString(optionValue)]),
        },
      });
    },
    selectAllFacetOptions(facetId) {
      const currentState = state();
      const facetsState = currentState.facetsState || {};

      set({
        // So that it only triggers refresh when facetsState is changed once (option is selected\deselected by user)
        facetsStateRefreshToken: uuidV4(),
        changedFacetId: facetId,
        activeFacetIds: { ...(state().activeFacetIds || {}), [facetId]: true },
        dirtyFacetIds: Array.from(new Set(state().dirtyFacetIds).add(facetId)),
        facetsState: {
          ...facetsState,
          [facetId]: toFacetState(
            currentState.facetOptions?.[facetId].map((option) =>
              valueToString(option.value)
            ) || []
          ),
        },
      });
    },

    facetsStateRefreshToken: null,

    isFacetsStateInitializedFromQueryParams: false,
    setIsFacetsStateInitializedFromQueryParams: (
      isFacetsStateInitializedFromQueryParams: boolean
    ) => set({ isFacetsStateInitializedFromQueryParams }),

    isInitialStateHandled: false,
    setIsInitialStateHandled: (isInitialStateHandled: boolean) =>
      set({ isInitialStateHandled }),

    clearFilters: () => {
      // Keep only non-lazy facets active so we don't re-load every lazy facet
      // after a reset (#6577).
      const activeFacetIds: Record<string, boolean> = {};
      (state().facets || []).forEach((facet) => {
        if (!facet.is_lazy) {
          activeFacetIds[facet.id] = true;
        }
      });
      return set({
        isInitialStateHandled: false,
        facetsState: {},
        facetsStateRefreshToken: uuidV4(),
        activeFacetIds,
        dirtyFacetIds: [],
      });
    },

    changedFacetId: null,
    setChangedFacetId: (facetId: string | null) =>
      set({ changedFacetId: facetId }),

    areOptionsReLoading: false,
    setAreOptionsReLoading: (isLoading: boolean) =>
      set({ areOptionsReLoading: isLoading }),

    areOptionsLoading: false,
    setAreOptionsLoading: (isLoading: boolean) =>
      set({ areOptionsLoading: isLoading }),
  }));
