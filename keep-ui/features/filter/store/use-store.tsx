import { createContext, useContext, useRef } from "react";
import { useStore } from "zustand";
import { createFacetStore, FacetState } from "./create-facets-store";
import { useFacetsLoadingStateHandler } from "./use-facets-loading-state-handler";
import { useQueriesHandler } from "./use-queries-handler";

export function useNewFacetStore() {
  const storeRef = useRef<ReturnType<typeof createFacetStore>>();

  if (!storeRef.current) {
    storeRef.current = createFacetStore(); // New store per provider
  }

  useFacetsLoadingStateHandler(storeRef.current);
  useQueriesHandler(storeRef.current);

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
