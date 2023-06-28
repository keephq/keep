"use client";
import { Icon, Select, SelectItem, Title } from "@tremor/react";
import { MagnifyingGlassIcon } from "@heroicons/react/20/solid";

export default function ProvidersLayout({
  children,
}: {
  children: React.ReactNode;
}) {
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
        <Icon
          icon={MagnifyingGlassIcon}
          color="gray"
          className="mr-5 hover:bg-gray-100"
        />
      </div>
      <div className="flex flex-col">{children}</div>
    </main>
  );
}
