import { createContext, useContext, useRef } from "react";
import { createStore, useStore } from "zustand";
import { v4 as uuidV4 } from "uuid";
import { FacetDto, FacetOptionDto } from "../models";

export type FacetState = {
  facets: FacetDto[] | null;
  facetOptions: Record<string, FacetOptionDto[]> | null;
  facetOptionsLoadingState: Record<string, string>;
  queriesState: {
    facetOptionQueries: Record<string, string> | null;
    filterCel: string | null;
  };
  facetCelState: Record<string, string> | null;
  facetsState: Record<string, any>;
  clearFiltersToken: string | null;
  changedFacetId: string | null;
  areOptionsReLoading: boolean;
  areOptionsLoading: boolean;
  setQueriesState: (
    filterCel: string,
    facetOptionQueries: Record<string, string>
  ) => void;
  setFacetOptionsLoadingState: (loadingState: Record<string, string>) => void;
  setChangedFacetId: (facetId: string | null) => void;
  setFacets: (facets: FacetDto[]) => void;
  setFacetOptions: (facetOptions: Record<string, FacetOptionDto[]>) => void;
  setFacetCelState: (facetId: string, cel: string) => void;
  setFacetState: (facetId: string, state: any) => void;
  clearFilters: () => void;
  setAreOptionsReLoading: (isLoading: boolean) => void;
  setAreOptionsLoading: (isLoading: boolean) => void;
};

export const createFacetStore = () =>
  createStore<FacetState>((set, state) => ({
    facets: null,
    facetOptions: null,
    facetOptionsLoadingState: {},
    queriesState: {
      facetOptionQueries: null,
      filterCel: null,
    },
    facetCelState: null,
    facetsState: {},
    clearFiltersToken: null,
    changedFacetId: null,
    areOptionsReLoading: false,
    areOptionsLoading: false,
    setQueriesState: (filterCel, facetOptionQueries) =>
      set({
        queriesState: {
          filterCel,
          facetOptionQueries,
        },
      }),
    setFacetOptionsLoadingState: (loadingState: Record<string, string>) =>
      set({ facetOptionsLoadingState: loadingState }),
    setFacetOptions: (facetOptions: Record<string, FacetOptionDto[]>) =>
      set({ facetOptions }),
    setChangedFacetId: (facetId: string | null) =>
      set({ changedFacetId: facetId }),
    setFacets: (facets: FacetDto[]) => set({ facets }),
    setFacetState(facetId, facetState) {
      set({
        facetsState: {
          ...(state().facetsState || {}),
          [facetId]: facetState,
        },
      });
    },
    setFacetCelState: (facetId: string, cel: string) =>
      set({
        facetCelState: {
          ...(state().facetCelState || {}),
          [facetId]: cel,
        },
      }),

    clearFilters: () => {
      return set({
        clearFiltersToken: uuidV4(),
        facetCelState: state().facets?.reduce(
          (acc, facet) => ({
            ...acc,
            [facet.id]: state().facetCelState?.[facet.id] || "",
          }),
          {}
        ),
      });
    },
    setAreOptionsReLoading: (isLoading: boolean) =>
      set({ areOptionsReLoading: isLoading }),
    setAreOptionsLoading: (isLoading: boolean) =>
      set({ areOptionsLoading: isLoading }),
  }));
