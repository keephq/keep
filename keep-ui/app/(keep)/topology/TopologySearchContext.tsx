"use client";
import React, { createContext, useContext, useState } from "react";

type TopologySearchContextType = {
  selectedObjectId: string | null;
  setSelectedObjectId: (id: string | null) => void;
  selectedApplicationIds: string[];
  setSelectedApplicationIds: (ids: string[]) => void;
};

const defaultContext: TopologySearchContextType = {
  selectedObjectId: "",
  setSelectedObjectId: () => {},
  selectedApplicationIds: [],
  setSelectedApplicationIds: () => {},
};

export const TopologySearchContext =
  createContext<TopologySearchContextType>(defaultContext);

export function useTopologySearchContext() {
  const context = useContext(TopologySearchContext);
  if (context === undefined) {
    throw new Error(
      "useTopologySearchContext must be used within a TopologySearchContextProvider"
    );
  }
  return context;
}

type TopologySearchProviderProps = {
  children: React.ReactNode;
  initialSelectedApplicationIds?: string[];
};

export const TopologySearchProvider: React.FC<TopologySearchProviderProps> = ({
  children,
  initialSelectedApplicationIds = [],
}) => {
  const [selectedServiceId, setSelectedServiceId] = useState<string | null>(
    null
  );
  const [selectedApplicationIds, setSelectedApplicationIds] = useState<
    string[]
  >(initialSelectedApplicationIds);

  return (
    <TopologySearchContext.Provider
      value={{
        selectedObjectId: selectedServiceId,
        setSelectedObjectId: setSelectedServiceId,
        selectedApplicationIds,
        setSelectedApplicationIds,
      }}
    >
      {children}
    </TopologySearchContext.Provider>
  );
};
