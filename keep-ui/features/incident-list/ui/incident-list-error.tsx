"use client";
import NotAuthorized from "@/app/not-authorized";
import { ErrorComponent } from "@/shared/ui";
interface IncidentListErrorProps {
  incidentError: any;
}

export const IncidentListError = ({
  incidentError,
}: IncidentListErrorProps) => {
  if (incidentError?.statusCode === 403) {
    return <NotAuthorized message={incidentError.message} />;
  }

  return <ErrorComponent error={incidentError} />;
};
