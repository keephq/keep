import { createContext, useContext, useEffect, useRef } from "react";
import { useStore } from "zustand";
import {
  createFacetsPanelStore,
  FacetsPanelState,
} from "./create-facets-store";
import { useFacetsLoadingStateHandler } from "./use-facets-loading-state-handler";
import { useQueriesHandler } from "./use-queries-handler";
import { useQueryParams } from "./use-query-params/use-query-params";
import { useFacetsConfig } from "./use-facets-config";
import { FacetsConfig } from "../models";
import { useInitialStateHandler } from "./use-initial-state-handler";
// import { useFacetsStateHandler } from "./use-facets-state-handler";

export function useNewFacetStore(facetsConfig: FacetsConfig | undefined) {
  const storeRef = useRef<ReturnType<typeof createFacetsPanelStore> | undefined>(undefined);

  if (!storeRef.current) {
    storeRef.current = createFacetsPanelStore(); // New store per provider
  }
  useFacetsConfig(facetsConfig, storeRef.current);
  useInitialStateHandler(storeRef.current);
  useFacetsLoadingStateHandler(storeRef.current);
  useQueriesHandler(storeRef.current);
  useQueryParams(storeRef.current);

  return storeRef.current;
}

const FacetStoreContext = createContext<ReturnType<
  typeof createFacetsPanelStore
> | null>(null);

export const FacetStoreProvider = ({
  store,
  children,
}: {
  store: ReturnType<typeof createFacetsPanelStore>;
  children: React.ReactNode;
}) => {
  return (
    <FacetStoreContext.Provider value={store}>
      {children}
    </FacetStoreContext.Provider>
  );
};

// Hook to access the scoped store
export function useExistingFacetsPanelStore<T>(
  selector: (state: FacetsPanelState) => T
): T {
  const store = useContext(FacetStoreContext);
  if (!store)
    throw new Error(
      "useExistingFacetsPanelStore must be used within FacetStoreProvider"
    );

  return useStore(store, selector);
}
