"use client";
import { PropsWithChildren } from "react";
import { ProvidersFilterByLabel } from "./components/providers-filter-by-label";
import { ProvidersSearch } from "./components/providers-search";
import { FilerContextProvider } from "./filter-context";

export default function ProvidersLayout({ children }: PropsWithChildren) {
  return (
    <FilerContextProvider>
      <main className="p-4">
        <div className="flex w-full justify-end mb-4 ml-2.5">
          <div className="flex">
            <ProvidersSearch />
            <ProvidersFilterByLabel />
          </div>
        </div>
        <div className="flex flex-col">{children}</div>
      </main>
    </FilerContextProvider>
  );
}
