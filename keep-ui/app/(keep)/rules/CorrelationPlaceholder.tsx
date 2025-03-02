import { Fragment, useState } from "react";
import { Button, Card, Subtitle, Title } from "@tremor/react";
import { CorrelationSidebar } from "./CorrelationSidebar";
import { PlaceholderSankey } from "./ui/PlaceholderSankey";

export const CorrelationPlaceholder = () => {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  const onCorrelationClick = () => {
    setIsSidebarOpen(true);
  };

  return (
    <Fragment>
      <Card className="flex flex-col items-center justify-center gap-y-8 h-full">
        <div className="text-center space-y-3">
          <Title className="text-2xl">No correlations yet</Title>
          <Subtitle className="text-gray-400">
            Start building correlations to group alerts into incidents.
          </Subtitle>
        </div>
        <Button
          className="mb-10"
          color="orange"
          onClick={() => onCorrelationClick()}
        >
          Create correlation
        </Button>
        <PlaceholderSankey className="max-w-full" />
      </Card>
      <CorrelationSidebar
        isOpen={isSidebarOpen}
        toggle={() => setIsSidebarOpen(!isSidebarOpen)}
      />
    </Fragment>
  );
};
