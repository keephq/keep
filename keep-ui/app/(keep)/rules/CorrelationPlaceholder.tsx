import { Fragment, useState } from "react";
import { Button, Card, Subtitle, Title } from "@tremor/react";
import { CorrelationSidebar } from "./CorrelationSidebar";
import { PlaceholderSankey } from "./ui/PlaceholderSankey";
import { PlusIcon } from "@heroicons/react/20/solid";

export const CorrelationPlaceholder = () => {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  const onCorrelationClick = () => {
    setIsSidebarOpen(true);
  };

  return (
    <Fragment>
      <div className="flex flex-col items-center justify-center gap-y-8 h-full bg-transparent">
        <div className="text-center space-y-3">
          <Title className="text-2xl">No Correlations Yet</Title>
          <Subtitle className="text-gray-400">
            Start building correlations to group alerts into incidents.
          </Subtitle>
        </div>
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
      </div>
      <CorrelationSidebar
        isOpen={isSidebarOpen}
        toggle={() => setIsSidebarOpen(!isSidebarOpen)}
      />
    </Fragment>
  );
};
