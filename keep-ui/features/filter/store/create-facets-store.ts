import { createStore } from "zustand";
import { v4 as uuidV4 } from "uuid";
import { FacetDto, FacetOptionDto } from "../models";

export type FacetState = {
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
  setFacetState: (facetId: string, state: any) => void;

  clearFiltersToken: string | null;
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
    setFacetState(facetId, facetState) {
      set({
        facetsState: {
          ...(state().facetsState || {}),
          [facetId]: facetState,
        },
      });
    },

    clearFiltersToken: null,
    clearFilters: () => {
      return set({
        clearFiltersToken: uuidV4(),
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
