"use client";
import { useState } from "react";
import { ServiceSearchContext } from "./service-search-context";

export default function Layout({ children }: { children: any }) {
  const [serviceQuery, setServiceQuery] = useState<string>("");
  const [selectedServiceId, setSelectedServiceId] = useState<string | null>(
    null
  );

  return (
    <ServiceSearchContext.Provider
      value={{
        serviceQuery,
        setServiceQuery,
        selectedServiceId,
        setSelectedServiceId,
      }}
    >
      {children}
    </ServiceSearchContext.Provider>
  );
}
