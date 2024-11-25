import { useCallback } from "react";
import { toast } from "react-toastify";
import { useSWRConfig } from "swr";
import { IncidentDto, Status } from "./models";
import { useApi } from "@/shared/lib/hooks/useApi";
import { KeepApiError } from "@/shared/lib/api/KeepApiError";

type UseIncidentActionsValue = {
  addIncident: (
    incident: IncidentCreateDto
  ) => Promise<IncidentDto | undefined>;
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
  const api = useApi();
  const { mutate } = useSWRConfig();

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
      try {
        const result = await api.post("/incidents", incident);
        mutateIncidentsList();
        toast.success("Incident created successfully");
        return result as IncidentDto;
      } catch (error) {
        toast.error(
          "Failed to create incident, please contact us if this issue persists."
        );
      }
    },
    [api, mutateIncidentsList]
  );

  const updateIncident = useCallback(
    async (
      incidentId: string,
      incident: IncidentUpdateDto,
      generatedByAi: boolean
    ) => {
      try {
        const result = await api.put(
          `/incidents/${incidentId}?generatedByAi=${generatedByAi}`,
          incident
        );

        mutateIncidentsList();
        mutateIncident(incidentId);
        toast.success("Incident updated successfully");

        return result;
      } catch (error) {
        toast.error(
          "Failed to update incident, please contact us if this issue persists."
        );
      }
    },
    [api, mutateIncident, mutateIncidentsList]
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
        const result = await api.post("/incidents/merge", {
          source_incident_ids: sourceIncidents.map((incident) => incident.id),
          destination_incident_id: destinationIncident.id,
        });
        toast.success("Incidents merged successfully!");
        mutateIncidentsList();
        return result;
      } catch (error) {
        if (error instanceof KeepApiError) {
          toast.error(
            "Failed to merge incidents, please contact us if this issue persists."
          );
        } else {
          toast.error("An error occurred while merging incidents.");
        }
      }
    },
    [api, mutateIncidentsList]
  );

  const deleteIncident = useCallback(
    async (incidentId: string, skipConfirmation = false) => {
      if (
        !skipConfirmation &&
        !confirm("Are you sure you want to delete this incident?")
      ) {
        return false;
      }
      try {
        const result = await api.delete(`/incidents/${incidentId}`);
        mutateIncidentsList();
        toast.success("Incident deleted successfully");
        return true;
      } catch (error) {
        toast.error("Failed to delete incident, contact us if this persists");
        return false;
      }
    },
    [api, mutateIncidentsList]
  );

  const changeStatus = useCallback(
    async (incidentId: string, status: Status, comment?: string) => {
      if (!status) {
        toast.error("Please select a new status.");
        return;
      }

      try {
        const result = await api.post(`/incidents/${incidentId}/status`, {
          status,
          comment,
        });

        toast.success("Incident status changed successfully!");
        mutateIncidentsList();
        return result;
      } catch (error) {
        if (error instanceof KeepApiError) {
          toast.error(
            "Failed to change incident status, please contact us if this issue persists."
          );
        } else {
          toast.error("An error occurred while changing incident status.");
        }
      }
    },
    [api, mutateIncidentsList]
  );

  // Is it used?
  const confirmPredictedIncident = useCallback(
    async (incidentId: string) => {
      try {
        const result = await api.post(`/incidents/${incidentId}/confirm`);
        mutateIncidentsList();
        mutateIncident(incidentId);
        toast.success("Predicted incident confirmed successfully");
        return result;
      } catch (error) {
        if (error instanceof KeepApiError) {
          toast.error(
            "Failed to confirm predicted incident, please contact us if this issue persists."
          );
        } else {
          toast.error("An error occurred while confirming predicted incident.");
        }
      }
    },
    [api, mutateIncident, mutateIncidentsList]
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
