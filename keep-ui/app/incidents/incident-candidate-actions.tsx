import { toast } from "react-toastify";
import { IncidentDto, PaginatedIncidentsDto } from "./models";
import { Session } from "next-auth";

interface Props {
  incidentId: string;
  mutate: () => void;
  session: Session | null;
  apiUrl: string;
}

export const handleConfirmPredictedIncident = async ({
  incidentId,
  mutate,
  session,
  apiUrl,
}: Props) => {
  const response = await fetch(`${apiUrl}/incidents/${incidentId}/confirm`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${session?.accessToken}`,
      "Content-Type": "application/json",
    },
  });
  if (response.ok) {
    await mutate();
    toast.success("Predicted incident confirmed successfully");
  } else {
    toast.error(
      "Failed to confirm predicted incident, please contact us if this issue persists."
    );
  }
};

export const deleteIncident = async ({
  incidentId,
  mutate,
  session,
  apiUrl,
  skipConfirmation = false,
}: Props & {
  skipConfirmation?: boolean;
}) => {
  if (
    !skipConfirmation &&
    !confirm("Are you sure you want to delete this incident?")
  ) {
    return;
  }
  const response = await fetch(`${apiUrl}/incidents/${incidentId}`, {
    method: "DELETE",
    headers: {
      Authorization: `Bearer ${session?.accessToken}`,
    },
  });

  if (response.ok) {
    await mutate();
    toast.success("Incident deleted successfully");
    return true;
  } else {
    toast.error("Failed to delete incident, contact us if this persists");
    return false;
  }
};
