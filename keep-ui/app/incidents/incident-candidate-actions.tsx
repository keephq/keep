import { getApiURL } from "../../utils/apiUrl";
import { toast } from "react-toastify";
import { IncidentDto, PaginatedIncidentsDto } from "./models";
import { Session } from "next-auth";

interface Props {
  incidentId: string;
  mutate: () => void;
  session: Session | null;
}

export const handleConfirmPredictedIncident = async ({
  incidentId,
  mutate,
  session,
}: Props) => {
  const apiUrl = getApiURL();
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
}: Props) => {
  const apiUrl = getApiURL();
  if (confirm("Are you sure you want to delete this incident?")) {
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
  }
};
