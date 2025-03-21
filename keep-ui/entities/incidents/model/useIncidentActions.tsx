import { useCallback } from "react";
import { toast } from "react-toastify";
import { useSWRConfig } from "swr";
import { IncidentDto, Severity, Status } from "./models";
import { useApi } from "@/shared/lib/hooks/useApi";
import { showErrorToast } from "@/shared/ui";

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
  changeSeverity: (
    incidentId: string,
    severity: Severity,
    comment?: string
  ) => Promise<void>;
  deleteIncident: (
    incidentId: string,
    skipConfirmation?: boolean
  ) => Promise<boolean>;
  bulkDeleteIncidents: (
    incidentIds: string[],
    skipConfirmation?: boolean
  ) => Promise<boolean>;
  mergeIncidents: (
    sourceIncidents: IncidentDto[],
    destinationIncident: IncidentDto
  ) => Promise<void>;
  invokeProviderMethod: (
    providerId: string,
    methodName: string,
    methodParams: { [key: string]: string | boolean | object }
  ) => Promise<any>;
  confirmPredictedIncident: (incidentId: string) => Promise<void>;
  unlinkAlertsFromIncident: (
    incidentId: string,
    alertFingerprints: string[],
    mutate?: () => void
  ) => Promise<void>;
  splitIncidentAlerts: (
    incidentId: string,
    alertFingerprints: string[],
    destinationIncidentId: string
  ) => Promise<void>;
  enrichIncident: (
    incidentId: string,
    enrichments: { [key: string]: any }
  ) => Promise<void>;
  mutateIncidentsList: () => void;
  mutateIncident: (incidentId: string) => void;
  assignIncident: (incidentId: string) => Promise<void>;
};

type IncidentCreateDto = {
  user_generated_name: string;
  user_summary: string;
  assignee: string;
  resolve_on: string;
  severity: Severity;
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

  const assignIncident = useCallback(
    async (incidentId: string) => {
      const result = await api.post(`/incidents/${incidentId}/assign`);
      mutateIncidentsList();
      mutateIncident(incidentId);
      return result;
    },
    [api, mutateIncident, mutateIncidentsList]
  );

  const invokeProviderMethod = useCallback(
    async (
      providerId: string,
      methodName: string,
      methodParams: { [key: string]: string | boolean | object }
    ) => {
      const result = await api.post(
        `/providers/${providerId}/invoke/${methodName}`,
        methodParams
      );
      return result;
    },
    [api]
  );

  const enrichIncident = useCallback(
    async (incidentId: string, enrichments: { [key: string]: any }) => {
      const result = await api.post(`/incidents/${incidentId}/enrich`, {
        enrichments: enrichments,
      });
      return result;
    },
    [api]
  );

  const addIncident = useCallback(
    async (incident: IncidentCreateDto) => {
      try {
        const result = await api.post("/incidents", incident);
        mutateIncidentsList();
        toast.success("Incident created successfully");
        return result as IncidentDto;
      } catch (error) {
        showErrorToast(
          error,
          "Failed to create incident, please contact us if this issue persists."
        );
        throw error;
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
        showErrorToast(error, "Failed to update incident");
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
        showErrorToast(new Error("Please select incidents to merge."));
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
        showErrorToast(error, "Failed to merge incidents");
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
        showErrorToast(error, "Failed to delete incident");
        return false;
      }
    },
    [api, mutateIncidentsList]
  );

  const bulkDeleteIncidents = useCallback(
    async (incidentIds: string[], skipConfirmation = false) => {
      if (
        !skipConfirmation &&
        !confirm(
          `Are you sure you want to delete ${
            incidentIds.length === 1
              ? "this incident?"
              : `${incidentIds.length} incidents?`
          }`
        )
      ) {
        return false;
      }
      try {
        const result = await api.delete("/incidents/bulk", {
          incident_ids: incidentIds,
        });
        mutateIncidentsList();
        toast.success("Incidents deleted successfully");
        return true;
      } catch (error) {
        showErrorToast(error, "Failed to delete incidents");
        return false;
      }
    },
    [api, mutateIncidentsList]
  );

  const changeStatus = useCallback(
    async (incidentId: string, status: Status, comment?: string) => {
      if (!status) {
        showErrorToast(new Error("Please select a new status."));
        return;
      }

      try {
        const result = await api.post(`/incidents/${incidentId}/status`, {
          status,
          comment,
        });

        toast.success("Incident status changed successfully!");
        mutateIncidentsList();
        mutateIncident(incidentId);
        return result;
      } catch (error) {
        showErrorToast(error, "Failed to change incident status");
      }
    },
    [api, mutateIncident, mutateIncidentsList]
  );

  const changeSeverity = useCallback(
    async (incidentId: string, severity: Severity, comment?: string) => {
      if (!severity) {
        showErrorToast(new Error("Please select a new severity."));
        return;
      }

      try {
        const result = await api.post(`/incidents/${incidentId}/severity`, {
          severity,
          comment,
        });

        toast.success("Incident severity changed successfully!");
        mutateIncident(incidentId);
        return result;
      } catch (error) {
        showErrorToast(error, "Failed to change incident severity");
      }
    },
    [api, mutateIncident]
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
        showErrorToast(error, "Failed to confirm predicted incident");
      }
    },
    [api, mutateIncident, mutateIncidentsList]
  );

  const unlinkAlertsFromIncident = useCallback(
    async (
      incidentId: string,
      alertFingerprints: string[],
      mutate?: () => void,
      {
        skipConfirmation = false,
      }: {
        skipConfirmation?: boolean;
      } = {}
    ) => {
      if (!alertFingerprints.length) {
        showErrorToast(new Error("Please select alerts to unlink."));
        return;
      }

      if (
        !skipConfirmation &&
        !confirm(
          `Are you sure you want to unlink ${
            alertFingerprints.length === 1
              ? "alert"
              : `${alertFingerprints.length} alerts`
          } from this incident?`
        )
      ) {
        return;
      }

      try {
        const result = await api.delete(
          `/incidents/${incidentId}/alerts`,
          alertFingerprints
        );
        if (mutate !== undefined) {
          await mutate();
        } else {
          await mutateIncidentsList();
          await mutateIncident(incidentId);
        }
        toast.success("Alerts unlinked from incident successfully");
        return result;
      } catch (error) {
        showErrorToast(error, "Failed to unlink alerts from incident");
      }
    },
    [api, mutateIncident, mutateIncidentsList]
  );

  const splitIncidentAlerts = useCallback(
    async (
      incidentId: string,
      alertFingerprints: string[],
      destinationIncidentId: string
    ) => {
      try {
        const result = await api.post(`/incidents/${incidentId}/split`, {
          alert_fingerprints: alertFingerprints,
          destination_incident_id: destinationIncidentId,
        });
        mutateIncidentsList();
        mutateIncident(incidentId);
        toast.success("Alerts split successfully");
        return result;
      } catch (error) {
        showErrorToast(error, "Failed to split incident alerts");
      }
    },
    [api, mutateIncident, mutateIncidentsList]
  );

  return {
    addIncident,
    updateIncident,
    changeStatus,
    changeSeverity,
    deleteIncident,
    bulkDeleteIncidents,
    mergeIncidents,
    confirmPredictedIncident,
    mutateIncidentsList,
    mutateIncident,
    unlinkAlertsFromIncident,
    splitIncidentAlerts,
    invokeProviderMethod,
    enrichIncident,
    assignIncident,
  };
}
