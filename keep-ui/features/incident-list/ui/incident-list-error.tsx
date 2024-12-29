import { Fragment } from "react";
import { Button, Subtitle, Title } from "@tremor/react";
import NotAuthorized from "@/app/not-authorized";

interface IncidentListErrorProps {
  incidentError: any;
}

export const IncidentListError = ({
  incidentError,
}: IncidentListErrorProps) => {
  if (incidentError?.statusCode === 403) {
    return <NotAuthorized message={incidentError.message} />;
  }

  return (
    <Fragment>
      <div className="flex flex-col items-center justify-center gap-y-8 h-full">
        <div className="text-center space-y-3">
          <Title className="text-2xl">Failed to load incidents</Title>
          <Subtitle className="text-gray-400">
            Error: {incidentError.message}
          </Subtitle>
          <Subtitle className="text-gray-400">
            {incidentError.proposedResolution ||
              "Please try again. If the issue persists, contact us"}
          </Subtitle>
          <Button
            color="orange"
            variant="secondary"
            onClick={() => window.open("https://slack.keephq.dev/", "_blank")}
          >
            Slack Us
          </Button>
        </div>
      </div>
    </Fragment>
  );
};
