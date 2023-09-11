"use client";
import { TextInput, Title } from "@tremor/react";
import { MagnifyingGlassIcon } from "@heroicons/react/20/solid";
import { useState } from "react";
import { LayoutContext } from "./context";

export default function ProvidersLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [providersSearchString, setProvidersSearchString] =
    useState<string>("");
  const searchProviderString = providersSearchString;
  return (
    <main className="p-4">
      <div className="flex w-full justify-between mb-4 ml-2.5">
        <div className="flex justify-center items-center">
          <Title>Providers</Title>
          {/* <Select className="h-8 w-44 ml-2.5" placeholder="Filter 1">
            <SelectItem value="filter-1">Filter 1</SelectItem>
          </Select>
          <Select className="h-8 w-44 ml-2.5" placeholder="Filter 2">
            <SelectItem value="filter-2">Filter 2</SelectItem>
          </Select> */}
        </div>
        <div>
          <TextInput
            id="search-providers"
            icon={MagnifyingGlassIcon}
            placeholder="Search Provider..."
            value={providersSearchString}
            onChange={(e) => setProvidersSearchString(e.target.value)}
          />
        </div>
      </div>
      <LayoutContext.Provider value={{ searchProviderString }}>
        <div className="flex flex-col">{children}</div>
      </LayoutContext.Provider>
    </main>
  );
}
