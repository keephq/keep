import { createContext, useContext, useRef } from "react";
import { create, createStore, useStore } from "zustand";
import { v4 as uuidV4 } from "uuid";
import { FacetDto } from "./models";

type FacetState = {
  facets: FacetDto[] | null;
  facetCelState: Record<string, string> | null;
  clearFiltersToken: string | null;
  setFacets: (facets: FacetDto[]) => void;
  setFacetCelState: (facetId: string, cel: string) => void;
  clearFilters: () => void;
};

const createFacetStore = () =>
  createStore<FacetState>((set, state) => ({
    facets: null,
    facetCelState: null,
    clearFiltersToken: null,
    setFacets: (facets: FacetDto[]) => set({ facets }),
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
  }));

export function useNewFacetStore() {
  const storeRef = useRef<ReturnType<typeof createFacetStore>>();

  if (!storeRef.current) {
    storeRef.current = createFacetStore(); // New store per provider
  }

  return storeRef.current;
}

const FacetStoreContext = createContext<ReturnType<
  typeof createFacetStore
> | null>(null);

export const FacetStoreProvider = ({
  store,
  children,
}: {
  store: ReturnType<typeof createFacetStore>;
  children: React.ReactNode;
}) => {
  return (
    <FacetStoreContext.Provider value={store}>
      {children}
    </FacetStoreContext.Provider>
  );
};

// Hook to access the scoped store
export function useExistingFacetStore<T>(
  selector: (state: FacetState) => T
): T {
  const store = useContext(FacetStoreContext);
  if (!store)
    throw new Error(
      "useExistingFacetStore must be used within FacetStoreProvider"
    );
  return useStore(store, selector);
}
