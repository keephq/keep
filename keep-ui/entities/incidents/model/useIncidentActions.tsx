import { useApiUrl, useConfig } from "@/utils/hooks/useConfig";
import { useHydratedSession as useSession } from "@/shared/lib/hooks/useHydratedSession";
import { useCallback } from "react";
import { useSWRConfig } from "swr";
import { IncidentDto, Status } from "./models";
import { ReadOnlyAwareToaster } from "@/shared/lib/ReadOnlyAwareToaster";
import { toast } from "react-toastify";

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
  confirmPredictedIncident: (incidentId: string) => Promise<void>;
  mutateIncidentsList: () => void;
  mutateIncident: (incidentId: string) => void;
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
  const { data: configData } = useConfig();

  const mutateIncidentsList = useCallback(
    () =>
      // Adding "?" to the key because the list always has a query param
      mutate((key) => typeof key === "string" && key.startsWith("/incidents?")),
    [mutate]
  );
  const mutateIncident = useCallback(
    (incidentId: string) =>
      mutate(
        (key) =>
          typeof key === "string" && key.startsWith(`/incidents/${incidentId}`)
      ),
    [mutate]
  );

  const addIncident = useCallback(
    async (incident: IncidentCreateDto) => {
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
        ReadOnlyAwareToaster.error(
          "Failed to create incident, please contact us if this issue persists.", configData
        );
      }
    },
    [apiUrl, mutateIncidentsList, session?.accessToken]
  );

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
        ReadOnlyAwareToaster.error(
          "Failed to update incident, please contact us if this issue persists.", configData
        );
      }
    },
    [apiUrl, mutateIncident, mutateIncidentsList, session?.accessToken]
  );

  const mergeIncidents = useCallback(
    async (
      sourceIncidents: IncidentDto[],
      destinationIncident: IncidentDto
    ) => {
      if (!sourceIncidents.length || !destinationIncident) {
        ReadOnlyAwareToaster.error("Please select incidents to merge.", configData);
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
          ReadOnlyAwareToaster.error("Failed to merge incidents.", configData);
        }
      } catch (error) {
        ReadOnlyAwareToaster.error("An error occurred while merging incidents.", configData);
      }
    },
    [apiUrl, mutateIncidentsList, session?.accessToken]
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
        ReadOnlyAwareToaster.error("Failed to delete incident, contact us if this persists", configData);
        return false;
      }
    },
    [apiUrl, mutateIncidentsList, session?.accessToken]
  );

  const changeStatus = useCallback(
    async (incidentId: string, status: Status, comment?: string) => {
      if (!status) {
        ReadOnlyAwareToaster.error("Please select a new status.", configData);
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
          ReadOnlyAwareToaster.error("Failed to change incident status.", configData);
        }
      } catch (error) {
        ReadOnlyAwareToaster.error("An error occurred while changing incident status.", configData);
      }
    },
    [apiUrl, mutateIncidentsList, session?.accessToken]
  );

  // Is it used?
  const confirmPredictedIncident = useCallback(
    async (incidentId: string) => {
      const response = await fetch(
        `${apiUrl}/incidents/${incidentId}/confirm`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${session?.accessToken}`,
            "Content-Type": "application/json",
          },
        }
      );
      if (response.ok) {
        mutateIncidentsList();
        mutateIncident(incidentId);
        toast.success("Predicted incident confirmed successfully");
      } else {
        ReadOnlyAwareToaster.error(
          "Failed to confirm predicted incident, please contact us if this issue persists.", 
          configData
        );
      }
    },
    [apiUrl, mutateIncident, mutateIncidentsList, session?.accessToken]
  );

  return {
    addIncident,
    updateIncident,
    changeStatus,
    deleteIncident,
    mergeIncidents,
    confirmPredictedIncident,
    mutateIncidentsList,
    mutateIncident,
  };
}
