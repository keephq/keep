import { TopologyApplication } from "@/app/(keep)/topology/model";
import { Card, Subtitle, Title } from "@tremor/react";

export function ApplicationCard({
  application,
  actionButtons,
}: {
  actionButtons: React.ReactNode;
  application: TopologyApplication;
}) {
  return (
    <Card className="flex flex-col">
      <div className="flex justify-between">
        <div>
          <Title>{application.name}</Title>
          <Subtitle>{application.description}</Subtitle>
          <div>
            Services:{" "}
            {application.services.map((service) => service.name).join(", ")}
          </div>
        </div>
        <div>{actionButtons}</div>
      </div>
    </Card>
  );
}
