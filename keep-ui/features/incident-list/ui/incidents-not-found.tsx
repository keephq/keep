import { Button } from "@tremor/react";
import { EmptyStateCard } from "@/shared/ui/EmptyState/EmptyStateCard";
import { MdFlashOn } from "react-icons/md";

interface Props {
  onClearFilters: () => void;
}

export const IncidentsNotFoundPlaceholder = ({ onClearFilters }: Props) => {
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
