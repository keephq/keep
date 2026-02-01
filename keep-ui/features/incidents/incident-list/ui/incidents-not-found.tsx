"use client";

import { Button } from "@tremor/react";
import { EmptyStateCard } from "@/shared/ui/EmptyState/EmptyStateCard";
import { MdFlashOn } from "react-icons/md";
import { useRouter } from "next/navigation";

interface Props {
  onClearFilters: () => void;
}

export const IncidentsNotFoundForFiltersPlaceholder = ({
  onClearFilters,
}: Props) => {
  return (
    <EmptyStateCard
      icon={MdFlashOn}
      title="No Incidents Matching the Filter"
      description="Clear filters to see all incidents"
    >
      <Button onClick={() => onClearFilters()}>Clear filters</Button>
    </EmptyStateCard>
  );
};

export const IncidentsNotFoundPlaceholder = () => {
  const router = useRouter();
  return (
    <EmptyStateCard
      icon={MdFlashOn}
      title="No Incidents Found"
      description="No active incidents found"
    >
      <div className="flex gap-2">
        <Button
          color="orange"
          variant="secondary"
          size="md"
          onClick={() => {
            router.push(`/alerts/feed`);
          }}
        >
          Correlate Alerts Manually
        </Button>
        <Button
          color="orange"
          variant="primary"
          size="md"
          onClick={() => {
            router.push(`/alerts/feed?createIncidentsFromLastAlerts=50`);
          }}
        >
          Try AI Correlation
        </Button>
      </div>
    </EmptyStateCard>
  );
};
