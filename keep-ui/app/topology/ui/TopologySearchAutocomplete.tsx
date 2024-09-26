import { useMemo } from "react";
import { useTopology } from "utils/hooks/useTopology";
import { useTopologyApplications } from "utils/hooks/useApplications";
import { AutocompleteInput } from "@/components/ui";
import { MagnifyingGlassIcon } from "@heroicons/react/24/solid";
import { AutocompleteInputProps } from "@/components/ui/AutocompleteInput";
import { TopologyServiceMinimal, TopologyApplication } from "../models";

type TopologySearchAutocompleteProps =
  | (Omit<
      AutocompleteInputProps<TopologyServiceMinimal | TopologyApplication>,
      "options" | "getId"
    > & {
      includeApplications: true;
      providerId?: string;
      service?: string;
      environment?: string;
    })
  | ({
      includeApplications: false;
      providerId?: string;
      service?: string;
      environment?: string;
    } & Omit<
      AutocompleteInputProps<TopologyServiceMinimal>,
      "options" | "getId"
    >);

export function TopologySearchAutocomplete({
  includeApplications = true,
  providerId,
  service,
  environment,
  ...props
}: Omit<TopologySearchAutocompleteProps, "options">) {
  const { topologyData } = useTopology(providerId, service, environment);
  const { applications } = useTopologyApplications();
  const searchOptions = useMemo(() => {
    const options: {
      label: string;
      value: TopologyServiceMinimal | TopologyApplication;
    }[] = [];
    topologyData?.forEach((service) => {
      options.push({
        label: service.display_name,
        value: {
          id: service.id,
          name: service.display_name,
          service: service.service,
        },
      });
    });
    if (!includeApplications) {
      return options;
    }
    applications.forEach((application) => {
      options.push({
        label: application.name,
        value: application,
      });
    });
    return options;
  }, [topologyData, includeApplications, applications]);

  return (
    <AutocompleteInput<TopologyServiceMinimal | TopologyApplication>
      icon={MagnifyingGlassIcon}
      options={searchOptions}
      getId={(option) => {
        if ("service" in option.value) {
          return option.value.service;
        }
        return option.value.id;
      }}
      {...props}
    />
  );
}
