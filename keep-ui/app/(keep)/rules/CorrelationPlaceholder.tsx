import { Fragment, useState } from "react";
import { Button, Card, Subtitle, Title } from "@tremor/react";
import { CorrelationSidebar } from "./CorrelationSidebar";
import { PlaceholderSankey } from "./ui/PlaceholderSankey";
import { PlusIcon } from "@heroicons/react/20/solid";
import { EmptyStateCard } from "@/shared/ui";

export const CorrelationPlaceholder = () => {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  const onCorrelationClick = () => {
    setIsSidebarOpen(true);
  };

  return (
    <Fragment>
      <EmptyStateCard
        noCard
        className="h-full"
        title="No Correlations Yet"
        description="Start building correlations to group alerts into incidents."
      >
        <Button
          className="mb-10"
          color="orange"
          variant="primary"
          size="md"
          onClick={() => onCorrelationClick()}
          icon={PlusIcon}
        >
          Create Correlation
        </Button>
        <PlaceholderSankey className="max-w-full" />
      </EmptyStateCard>
      <CorrelationSidebar
        isOpen={isSidebarOpen}
        toggle={() => setIsSidebarOpen(!isSidebarOpen)}
      />
    </Fragment>
  );
};
