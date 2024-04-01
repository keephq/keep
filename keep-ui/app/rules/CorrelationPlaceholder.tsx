import { Fragment, useState } from "react";
import { Button, Card, Subtitle, Title } from "@tremor/react";
import { CreateCorrelationSidebar } from "./CreateCorrelationSidebar";

export const CorrelationPlaceholder = () => {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  const onCreateCorrelationClick = () => {
    setIsSidebarOpen(true);
  };

  return (
    <Fragment>
      <Card className="flex flex-col items-center justify-center gap-y-8 h-full">
        <div className="text-center space-y-3">
          <Title className="text-2xl">No Correlations Yet</Title>
          <Subtitle className="text-gray-400">
            Start building correlation and get all relevant alerts in one
            dedicated place
          </Subtitle>
        </div>
        <Button color="orange" onClick={() => onCreateCorrelationClick()}>
          Create Correlation
        </Button>
      </Card>
      <CreateCorrelationSidebar
        isOpen={isSidebarOpen}
        toggle={() => setIsSidebarOpen(!isSidebarOpen)}
      />
    </Fragment>
  );
};
