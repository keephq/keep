import { useMemo } from "react";
import {
  useTopology,
  useTopologyApplications,
  TopologyServiceMinimal,
  TopologyApplication,
  TopologyApplicationMinimal,
} from "@/app/(keep)/topology/model";
import { AutocompleteInput } from "@/components/ui";
import { MagnifyingGlassIcon } from "@heroicons/react/24/solid";
import {
  AutocompleteInputProps,
  Option,
} from "@/components/ui/AutocompleteInput";

type BaseProps = {
  excludeServiceIds?: string[];
  providerIds?: string[];
  services?: string[];
  environment?: string;
};

type WithApplications = BaseProps &
  Omit<
    AutocompleteInputProps<TopologyServiceMinimal | TopologyApplicationMinimal>,
    "options" | "getId"
  > & {
    includeApplications: true;
  };

type WithoutApplications = BaseProps &
  Omit<AutocompleteInputProps<TopologyServiceMinimal>, "options" | "getId"> & {
    includeApplications: false;
  };

type TopologySearchAutocompleteProps = WithApplications | WithoutApplications;

export function TopologySearchAutocomplete({
  includeApplications,
  excludeServiceIds,
  providerIds,
  services,
  environment,
  onSelect,
  ...props
}: Omit<TopologySearchAutocompleteProps, "options">) {
  const { topologyData } = useTopology({ providerIds, services, environment });
  const { applications } = useTopologyApplications();
  const searchOptions = useMemo(() => {
    const serviceOptions =
      topologyData
        ?.filter(
          (service) =>
            service.service && !excludeServiceIds?.includes(service.service)
        )
        .map((service) => ({
          label: service.display_name,
          value: {
            id: service.id,
            name: service.display_name,
            service: service.service,
          },
        })) || [];
    if (!includeApplications) {
      return serviceOptions;
    }
    const applicationOptions = applications.map((application) => ({
      label: application.name,
      value: application,
    }));
    return [...serviceOptions, ...applicationOptions];
  }, [topologyData, includeApplications, applications, excludeServiceIds]);

  if (includeApplications) {
    return (
      <AutocompleteInput<TopologyServiceMinimal | TopologyApplication>
        icon={MagnifyingGlassIcon}
        options={searchOptions}
        getId={(option) => {
          return option.value.id.toString();
        }}
        onSelect={(option) => {
          // Type guard to check if the option is a TopologyServiceMinimal
          if ("service" in option.value) {
            onSelect(option as Option<TopologyServiceMinimal>);
          } else {
            // TODO: Fix type
            // @ts-ignore
            onSelect(option as Option<TopologyApplicationMinimal>);
          }
        }}
        {...props}
      />
    );
  }

  return (
    <AutocompleteInput<TopologyServiceMinimal>
      icon={MagnifyingGlassIcon}
      options={searchOptions as Option<TopologyServiceMinimal>[]}
      getId={(option) => {
        return option.value.service;
      }}
      onSelect={(option) => {
        onSelect(option as Option<TopologyServiceMinimal>);
      }}
      {...props}
    />
  );
}
