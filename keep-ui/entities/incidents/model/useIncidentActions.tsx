import { IncidentDto, Status } from "@/app/incidents/models";
import { useApiUrl } from "@/utils/hooks/useConfig";
import { useSession } from "next-auth/react";
import { useCallback } from "react";
import { toast } from "react-toastify";
import { useSWRConfig } from "swr";

type UseIncidentActionsValue = {
  addIncident: (incident: IncidentCreateDto) => Promise<IncidentDto>;
  updateIncident: (
    incidentId: string,
    incident: IncidentUpdateDto,
    generatedByAi: boolean
  ) => Promise<void>;
  changeStatus: (
    incidentId: string,
    status: Status,
    comment?: string
  ) => Promise<void>;
  deleteIncident: (
    incidentId: string,
    skipConfirmation?: boolean
  ) => Promise<boolean>;
  mergeIncidents: (
    sourceIncidents: IncidentDto[],
    destinationIncident: IncidentDto
  ) => Promise<void>;
};

type IncidentCreateDto = {
  user_generated_name: string;
  user_summary: string;
  assignee: string;
};

type IncidentUpdateDto = Partial<IncidentCreateDto> &
  Partial<{
    same_incident_in_the_past_id: string | null;
  }>;

export function useIncidentActions(): UseIncidentActionsValue {
  const apiUrl = useApiUrl();
  const { data: session } = useSession();
  const { mutate } = useSWRConfig();

  // Adding "?" to the key because the list always has a query param
  const mutateIncidentsList = () =>
    mutate((key) => typeof key === "string" && key.startsWith("/incidents?"));
  const mutateIncident = (incidentId: string) =>
    mutate(`/incidents/${incidentId}`);

  const addIncident = useCallback(async (incident: IncidentCreateDto) => {
    const response = await fetch(`${apiUrl}/incidents`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${session?.accessToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(incident),
    });
    if (response.ok) {
      mutateIncidentsList();
      toast.success("Incident created successfully");
      return await response.json();
    } else {
      toast.error(
        "Failed to create incident, please contact us if this issue persists."
      );
    }
  }, []);

  const updateIncident = useCallback(
    async (
      incidentId: string,
      incident: IncidentUpdateDto,
      generatedByAi: boolean
    ) => {
      const response = await fetch(
        `${apiUrl}/incidents/${incidentId}?generatedByAi=${generatedByAi}`,
        {
          method: "PUT",
          headers: {
            Authorization: `Bearer ${session?.accessToken}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify(incident),
        }
      );
      if (response.ok) {
        mutateIncidentsList();
        mutateIncident(incidentId);
        toast.success("Incident updated successfully");
      } else {
        toast.error(
          "Failed to update incident, please contact us if this issue persists."
        );
      }
    },
    []
  );

  const mergeIncidents = useCallback(
    async (
      sourceIncidents: IncidentDto[],
      destinationIncident: IncidentDto
    ) => {
      if (!sourceIncidents.length || !destinationIncident) {
        toast.error("Please select incidents to merge.");
        return;
      }

      try {
        const response = await fetch(`${apiUrl}/incidents/merge`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${session?.accessToken}`,
          },
          body: JSON.stringify({
            source_incident_ids: sourceIncidents.map((incident) => incident.id),
            destination_incident_id: destinationIncident.id,
          }),
        });

        if (response.ok) {
          toast.success("Incidents merged successfully!");
          mutateIncidentsList();
        } else {
          toast.error("Failed to merge incidents.");
        }
      } catch (error) {
        toast.error("An error occurred while merging incidents.");
      }
    },
    []
  );

  const deleteIncident = useCallback(
    async (incidentId: string, skipConfirmation = false) => {
      if (
        !skipConfirmation &&
        !confirm("Are you sure you want to delete this incident?")
      ) {
        return false;
      }
      const response = await fetch(`${apiUrl}/incidents/${incidentId}`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${session?.accessToken}`,
        },
      });

      if (response.ok) {
        mutateIncidentsList();
        toast.success("Incident deleted successfully");
        return true;
      } else {
        toast.error("Failed to delete incident, contact us if this persists");
        return false;
      }
    },
    []
  );

  const changeStatus = useCallback(
    async (incidentId: string, status: Status, comment?: string) => {
      if (!status) {
        toast.error("Please select a new status.");
        return;
      }

      try {
        const response = await fetch(
          `${apiUrl}/incidents/${incidentId}/status`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${session?.accessToken}`,
            },
            body: JSON.stringify({
              status,
              comment,
            }),
          }
        );

        if (response.ok) {
          toast.success("Incident status changed successfully!");
          mutateIncidentsList();
        } else {
          toast.error("Failed to change incident status.");
        }
      } catch (error) {
        toast.error("An error occurred while changing incident status.");
      }
    },
    []
  );

  return {
    addIncident,
    updateIncident,
    changeStatus,
    deleteIncident,
    mergeIncidents,
  };
}
