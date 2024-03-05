"use client";
import { MultiSelect, MultiSelectItem, TextInput, Title } from "@tremor/react";
import { MagnifyingGlassIcon, TagIcon } from "@heroicons/react/20/solid";
import { useState } from "react";
import { LayoutContext } from "./context";
import { useSearchParams } from "next/navigation";

export default function ProvidersLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [providersSearchString, setProvidersSearchString] =
    useState<string>("");
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const searchParams = useSearchParams();
  const labels = searchParams?.get("labels");
  const labelArray = labels ? labels.split(',').filter(label => label) : [];

  // update the selected tags with the labels from the url
  if (labelArray.length > 0 && selectedTags.length === 0) {
    setSelectedTags(labelArray);
  }

  const searchProviderString = providersSearchString;
  return (
    <main className="p-4">
      <div className="flex w-full justify-between mb-4 ml-2.5">
        <div className="flex justify-center items-center">
          {/* <Title>Providers</Title> */}
          {/* <Select className="h-8 w-44 ml-2.5" placeholder="Filter 1">
            <SelectItem value="filter-1">Filter 1</SelectItem>
          </Select>
          <Select className="h-8 w-44 ml-2.5" placeholder="Filter 2">
            <SelectItem value="filter-2">Filter 2</SelectItem>
          </Select> */}
        </div>
        <div className="flex">
          <TextInput
            id="search-providers"
            icon={MagnifyingGlassIcon}
            placeholder="Filter providers..."
            value={providersSearchString}
            onChange={(e) => setProvidersSearchString(e.target.value)}
          />
          <MultiSelect
            onValueChange={setSelectedTags}
            value={selectedTags}
            placeholder="Filter by label..."
            className="max-w-xs ml-2.5"
            icon={TagIcon}
          >
            <MultiSelectItem value="alert">Alert</MultiSelectItem>
            <MultiSelectItem value="messaging">Messaging</MultiSelectItem>
            <MultiSelectItem value="ticketing">Ticketing</MultiSelectItem>
            <MultiSelectItem value="data">Data</MultiSelectItem>
          </MultiSelect>
        </div>
      </div>
      <LayoutContext.Provider value={{ searchProviderString, selectedTags }}>
        <div className="flex flex-col">{children}</div>
      </LayoutContext.Provider>
    </main>
  );
}
