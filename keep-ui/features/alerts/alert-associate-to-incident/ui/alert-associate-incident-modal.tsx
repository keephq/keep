import Modal from "@/components/ui/Modal";
import { Button, Divider, Title } from "@tremor/react";
import { CreateOrUpdateIncidentForm } from "features/incidents/create-or-update-incident";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { toast } from "react-toastify";
import { useIncidents, usePollIncidents } from "@/utils/hooks/useIncidents";
import Loading from "@/app/(keep)/loading";
import { AlertDto } from "@/entities/alerts/model";
import {
  getIncidentName,
  getIncidentNameWithCreationTime,
} from "@/entities/incidents/lib/utils";
import { useApi } from "@/shared/lib/hooks/useApi";
import { Select, showErrorToast } from "@/shared/ui";
import { IncidentDto, Status } from "@/entities/incidents/model";
import { useI18n } from "@/i18n/hooks/useI18n";

interface AlertAssociateIncidentModalProps {
  isOpen: boolean;
  handleSuccess: () => void;
  handleClose: () => void;
  alerts: Array<AlertDto>;
}

export const AlertAssociateIncidentModal = ({
  isOpen,
  handleSuccess,
  handleClose,
  alerts,
}: AlertAssociateIncidentModalProps) => {
  const { t } = useI18n();
  const [createIncident, setCreateIncident] = useState(false);

  const {
    data: incidents,
    isLoading,
    mutate,
  } = useIncidents({ candidate: false, predicted: null, limit: 100 });
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
        toast.success(t("alerts.associateIncident.toastSuccess"));
      } catch (error) {
        showErrorToast(
          error,
          t("alerts.associateIncident.toastFailed")
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

  const filterIncidents = (incident: IncidentDto) => {
    return (
      incident.status === Status.Firing ||
      incident.status === Status.Acknowledged
    );
  };

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
          <Title className="text-md text-gray-500 my-4">{t("alerts.associateIncident.noIncidents")}</Title>

          <Button
            className="flex-1"
            color="orange"
            onClick={showCreateIncidentForm}
          >
            {t("alerts.associateIncident.createNew")}
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
          placeholder={t("alerts.associateIncident.selectIncident")}
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
          options={incidents.items?.filter(filterIncidents).map((incident) => ({
            value: incident.id,
            label: getIncidentNameWithCreationTime(incident),
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
            {t("alerts.associateIncident.associateButton", { count: alerts.length })}
          </Button>

          <Button
            className="flex-1"
            color="orange"
            variant="secondary"
            onClick={showCreateIncidentForm}
          >
            {t("alerts.associateIncident.createNew")}
          </Button>
        </div>
      </div>
    );
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title={t("alerts.associateIncident.title")}
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
