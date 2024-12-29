import Modal from "@/components/ui/Modal";
import { Button, Divider, Title } from "@tremor/react";
import { CreateOrUpdateIncidentForm } from "@/features/create-or-update-incident";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { toast } from "react-toastify";
import {
  useIncidents,
  usePollIncidents,
} from "../../../utils/hooks/useIncidents";
import Loading from "@/app/(keep)/loading";
import { AlertDto } from "@/entities/alerts/model";
import { getIncidentName } from "@/entities/incidents/lib/utils";
import { useApi } from "@/shared/lib/hooks/useApi";
import { Select, showErrorToast } from "@/shared/ui";

interface AlertAssociateIncidentModalProps {
  isOpen: boolean;
  handleSuccess: () => void;
  handleClose: () => void;
  alerts: Array<AlertDto>;
}

const AlertAssociateIncidentModal = ({
  isOpen,
  handleSuccess,
  handleClose,
  alerts,
}: AlertAssociateIncidentModalProps) => {
  const [createIncident, setCreateIncident] = useState(false);

  const { data: incidents, isLoading, mutate } = useIncidents(true, 100);
  usePollIncidents(mutate);

  const [selectedIncident, setSelectedIncident] = useState<
    string | undefined
  >();
  const api = useApi();

  const associateAlertsHandler = useCallback(
    async (incidentId: string) => {
      try {
        const response = await api.post(
          `/incidents/${incidentId}/alerts`,
          alerts.map(({ fingerprint }) => fingerprint)
        );
        handleSuccess();
        await mutate();
        toast.success("Alerts associated with incident successfully");
      } catch (error) {
        showErrorToast(
          error,
          "Failed to associated alerts with incident, please contact us if this issue persists."
        );
      }
    },
    [alerts, api, handleSuccess, mutate]
  );

  const handleAssociateAlerts = (e: FormEvent) => {
    e.preventDefault();
    if (selectedIncident) associateAlertsHandler(selectedIncident);
  };

  const showCreateIncidentForm = useCallback(() => setCreateIncident(true), []);

  const hideCreateIncidentForm = useCallback(
    () => setCreateIncident(false),
    []
  );

  const onIncidentCreated = useCallback(
    (incidentId: string) => {
      hideCreateIncidentForm();
      handleClose();
      associateAlertsHandler(incidentId);
    },
    [associateAlertsHandler, handleClose, hideCreateIncidentForm]
  );

  // reset modal state after closing
  useEffect(() => {
    if (!isOpen) {
      hideCreateIncidentForm();
      setSelectedIncident(undefined);
    }
  }, [hideCreateIncidentForm, isOpen]);

  // if this modal should not be open, do nothing
  if (!alerts) {
    return null;
  }

  const renderSelectIncidentForm = () => {
    if (!incidents || incidents.items.length === 0) {
      return (
        <div className="flex flex-col">
          <Title className="text-md text-gray-500 my-4">No incidents yet</Title>

          <Button
            className="flex-1"
            color="orange"
            onClick={showCreateIncidentForm}
          >
            Create a new incident
          </Button>
        </div>
      );
    }

    const selectedIncidentInstance = incidents.items.find(
      (incident) => incident.id === selectedIncident
    );

    return (
      <div className="h-full justify-center">
        <Select
          className="my-2.5"
          placeholder="Select incident"
          value={
            selectedIncidentInstance
              ? {
                  value: selectedIncident,
                  label: getIncidentName(selectedIncidentInstance),
                }
              : null
          }
          onChange={(selectedOption) =>
            setSelectedIncident(selectedOption?.value)
          }
          options={incidents.items?.map((incident) => ({
            value: incident.id,
            label: getIncidentName(incident),
          }))}
        />
        <Divider />
        <div className="flex items-center justify-between gap-6">
          <Button
            className="flex-1"
            color="orange"
            onClick={handleAssociateAlerts}
            disabled={!selectedIncidentInstance}
          >
            Associate {alerts.length} alert{alerts.length > 1 ? "s" : ""}
          </Button>

          <Button
            className="flex-1"
            color="orange"
            variant="secondary"
            onClick={showCreateIncidentForm}
          >
            Create a new incident
          </Button>
        </div>
      </div>
    );
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title="Associate alerts to incident"
      className="w-[600px]"
    >
      <div className="relative">
        {isLoading ? (
          <Loading />
        ) : createIncident ? (
          <CreateOrUpdateIncidentForm
            incidentToEdit={null}
            createCallback={onIncidentCreated}
            exitCallback={hideCreateIncidentForm}
          />
        ) : (
          renderSelectIncidentForm()
        )}
      </div>
    </Modal>
  );
};

export default AlertAssociateIncidentModal;
