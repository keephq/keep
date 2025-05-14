import { createContext, useContext, useEffect, useRef } from "react";
import { useStore } from "zustand";
import { createFacetStore, FacetState } from "./create-facets-store";
import { useFacetsLoadingStateHandler } from "./use-facets-loading-state-handler";
import { useQueriesHandler } from "./use-queries-handler";
import { useQueryParams } from "./use-query-params";
import { useFacetsConfig } from "./use-facets-config";
import { FacetsConfig } from "../models";
import { useInitialStateHandler } from "./use-initial-state-handler";

export function useNewFacetStore(facetsConfig: FacetsConfig | undefined) {
  const storeRef = useRef<ReturnType<typeof createFacetStore>>();

  if (!storeRef.current) {
    storeRef.current = createFacetStore(); // New store per provider
  }
  useFacetsConfig(facetsConfig, storeRef.current);
  useInitialStateHandler(storeRef.current);
  useFacetsLoadingStateHandler(storeRef.current);
  useQueriesHandler(storeRef.current);
  useQueryParams(storeRef.current);

  const facetsState = useStore(storeRef.current, (state) => state.facetsState);

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
