"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import { useWebsocket } from "@/utils/hooks/usePusher";
import { toast } from "react-toastify";

interface TopologyUpdate {
  providerType: string;
  providerId: string;
}

const TopologyPollingContext = createContext<number>(0);

// Using this provider to avoid polling on every render
export const TopologyPollingContextProvider: React.FC<{
  children: React.ReactNode;
}> = ({ children }) => {
  const [pollTopology, setPollTopology] = useState(0);
  const { bind, unbind } = useWebsocket();

  useEffect(() => {
    const handleIncoming = (data: TopologyUpdate) => {
      toast.success(
        `Topology pulled from ${data.providerId} (${data.providerType})`,
        { position: "top-right" }
      );
      setPollTopology((prev) => prev + 1);
    };

    bind("topology-update", handleIncoming);
    return () => {
      unbind("topology-update", handleIncoming);
    };
  }, [bind, unbind]);

  return (
    <TopologyPollingContext.Provider value={pollTopology}>
      {children}
    </TopologyPollingContext.Provider>
  );
};

export function useTopologyPollingContext() {
  const context = useContext(TopologyPollingContext);
  if (context === undefined) {
    throw new Error(
      "useTopologyContext must be used within a TopologyContextProvider"
    );
  }
  return context;
}
