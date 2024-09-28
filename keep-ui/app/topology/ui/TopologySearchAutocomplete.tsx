import { useMemo } from "react";
import { useTopology } from "utils/hooks/useTopology";
import { useTopologyApplications } from "utils/hooks/useApplications";
import { AutocompleteInput } from "@/components/ui";
import { MagnifyingGlassIcon } from "@heroicons/react/24/solid";
import {
  AutocompleteInputProps,
  Option,
} from "@/components/ui/AutocompleteInput";
import {
  TopologyServiceMinimal,
  TopologyApplication,
  TopologyApplicationMinimal,
} from "../models";

type TopologySearchAutocompleteWithApplicationsProps = Omit<
  AutocompleteInputProps<TopologyServiceMinimal | TopologyApplicationMinimal>,
  "options" | "getId"
> & {
  includeApplications: true;
  providerId?: string;
  service?: string;
  environment?: string;
};

type TopologySearchAutocompleteWithoutApplicationsProps = Omit<
  AutocompleteInputProps<TopologyServiceMinimal>,
  "options" | "getId"
> & {
  includeApplications: false;
  providerId?: string;
  service?: string;
  environment?: string;
};

type TopologySearchAutocompleteProps =
  | TopologySearchAutocompleteWithApplicationsProps
  | TopologySearchAutocompleteWithoutApplicationsProps;

export function TopologySearchAutocomplete({
  includeApplications,
  providerId,
  service,
  environment,
  onSelect,
  ...props
}: Omit<TopologySearchAutocompleteProps, "options">) {
  const { topologyData } = useTopology({ providerId, service, environment });
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
      // TODO: Fix type
      // @ts-ignore
      options={searchOptions}
      getId={(option) => {
        return option.value.service;
      }}
      {...props}
    />
  );
}
