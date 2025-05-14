import { createStore } from "zustand";
import { v4 as uuidV4 } from "uuid";
import { FacetDto, FacetOptionDto, FacetsConfig } from "../models";

export type FacetState = {
  facetsConfig: FacetsConfig | null;
  setFacetsConfig: (facetsConfig: FacetsConfig) => void;

  facets: FacetDto[] | null;
  setFacets: (facets: FacetDto[]) => void;

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

  facetsState: Record<string, any>;

  patchFacetsState: (facetsStatePatch: Record<string, any>) => void;
  setFacetState: (facetId: string, state: any) => void;

  areFacetOptionsHandled: boolean;
  setAreFacetOptionsHandled: (areFacetOptionsHandled: boolean) => void;

  facetsStateRefreshToken: string | null;

  areQueryparamsSet: boolean;
  setAreQueryparamsSet: (areQueryparamsSet: boolean) => void;

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

export const createFacetStore = () =>
  createStore<FacetState>((set, state) => ({
    facetsConfig: null,
    setFacetsConfig: (facetsConfig: FacetsConfig) => set({ facetsConfig }),

    facets: null,
    setFacets: (facets: FacetDto[]) => set({ facets }),

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

    facetsState: {},
    patchFacetsState: (facetsStatePatch) => {
      set({
        // So that it only triggers refresh when facetsState is patched once
        facetsStateRefreshToken: state().facetsStateRefreshToken || uuidV4(),
        facetsState: {
          ...(state().facetsState || {}),
          ...facetsStatePatch,
        },
      });
    },
    setFacetState(facetId, facetState) {
      set({
        // So that it only triggers refresh when facetsState is changed once (option is selected\deselected by user)
        facetsStateRefreshToken: uuidV4(),
        facetsState: {
          ...(state().facetsState || {}),
          [facetId]: facetState,
        },
      });
    },

    areFacetOptionsHandled: false,
    setAreFacetOptionsHandled: (areFacetOptionsHandled) =>
      set({
        areFacetOptionsHandled,
      }),

    facetsStateRefreshToken: null,

    areQueryparamsSet: false,
    setAreQueryparamsSet: (areQueryparamsSet: boolean) =>
      set({ areQueryparamsSet }),

    isInitialStateHandled: false,
    setIsInitialStateHandled: (isInitialStateHandled: boolean) =>
      set({ isInitialStateHandled }),

    clearFilters: () => {
      return set({
        isInitialStateHandled: false,
        facetsState: {},
        facetsStateRefreshToken: uuidV4(),
        areFacetOptionsHandled: false,
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
