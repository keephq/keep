"use client";
import { Subtitle, TextInput, Title } from "@tremor/react";
import { useState } from "react";
import { ServiceSearchContext } from "./service-search-context";

export default function Layout({ children }: { children: any }) {
  const [serviceInput, setServiceInput] = useState<string>("");

  return (
    <main className="p-4 md:p-10 mx-auto max-w-full h-full">
      <div className="flex w-full justify-between">
        <div>
          <Title>Service Topology</Title>
          <Subtitle>
            Data describing the topology of components in your environment.
          </Subtitle>
        </div>
        <TextInput
          placeholder="Search for a service"
          value={serviceInput}
          onValueChange={setServiceInput}
          className="w-64 mt-2"
        />
      </div>
      <ServiceSearchContext.Provider value={serviceInput}>
        {children}
      </ServiceSearchContext.Provider>
    </main>
  );
}
