import { Fragment, useState } from "react";
import { Button, Card, Subtitle, Title } from "@tremor/react";
// import { CorrelationSidebar } from "./CorrelationSidebar";
import { DeduplicationSankey } from "./DeduplicationSankey";

export const DeduplicationPlaceholder = () => {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  const onCorrelationClick = () => {
    setIsSidebarOpen(true);
  };

  return (
    <Fragment>
      <Card className="flex flex-col items-center justify-center gap-y-8 h-full">
        <div className="text-center space-y-3">
          <Title className="text-2xl">No Deduplications Yet</Title>
          <Subtitle className="text-gray-400">
            Reduce noise by creatiing deduplications.
          </Subtitle>
          <Subtitle className="text-gray-400">
            Start sending alerts or connect providers to create deduplication
            rules.
          </Subtitle>
        </div>
        <DeduplicationSankey className="max-w-full" />
      </Card>
    </Fragment>
  );
};
