"use client";
import { Subtitle, Title } from "@tremor/react";
import { useContext, useMemo } from "react";
import { ServiceSearchContext } from "./service-search-context";
import { AutocompleteInput } from "@/components/ui";
import { TopologyMap } from "./ui/topology-map";
import { useTopology } from "utils/hooks/useTopology";
import { MagnifyingGlassIcon } from "@heroicons/react/24/solid";

interface TopologyPageProps {
  providerId?: string;
  service?: string;
  environment?: string;
}

export default function TopologyPage({
  providerId,
  service,
  environment,
}: TopologyPageProps) {
  const { topologyData, error, isLoading } = useTopology(
    providerId,
    service,
    environment
  );
  const searchOptions = useMemo(() => {
    const createdApplications = new Set<string>();
    const options: { label: string; value: string }[] = [];
    topologyData?.forEach((service) => {
      options.push({
        label: service.display_name,
        value: service.service.toString(),
      });
      if (
        service.applicationObject &&
        !createdApplications.has(service.applicationObject.name)
      ) {
        createdApplications.add(service.applicationObject.name);
        options.push({
          label: service.applicationObject.name,
          value: service.applicationObject.name,
        });
      }
    });
    return options;
  }, [topologyData]);
  const {
    serviceQuery,
    setServiceQuery,
    selectedServiceId,
    setSelectedServiceId,
  } = useContext(ServiceSearchContext);
  return (
    <main className="flex flex-col h-full">
      <div className="flex w-full justify-between">
        <div>
          <Title>Service Topology</Title>
          <Subtitle>
            Data describing the topology of components in your environment.
          </Subtitle>
        </div>
        <AutocompleteInput<string>
          icon={MagnifyingGlassIcon}
          options={searchOptions}
          placeholder="Search for a service"
          onSelect={(option, clearInput) => {
            setSelectedServiceId(option.value);
            clearInput();
          }}
          className="w-64 mt-2"
        />
      </div>
      <ServiceSearchContext.Provider
        value={{
          serviceQuery,
          setServiceQuery,
          selectedServiceId,
          setSelectedServiceId,
        }}
      >
        <TopologyMap
          topologyData={topologyData}
          isLoading={isLoading}
          error={error}
        />
      </ServiceSearchContext.Provider>
    </main>
  );
}
