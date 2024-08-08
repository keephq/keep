import Modal from "@/components/ui/Modal";
import { Button, Divider, Select, SelectItem, Title } from "@tremor/react";
import CreateOrUpdateIncident from "app/incidents/create-or-update-incident";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { toast } from "react-toastify";
import { getApiURL } from "../../utils/apiUrl";
import { useIncidents, usePollIncidents } from "../../utils/hooks/useIncidents";
import Loading from "../loading";
import { AlertDto } from "./models";

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

  const [selectedIncident, setSelectedIncident] = useState<string | undefined>();
  // get the token
  const { data: session } = useSession();
  const router = useRouter();

  const associateAlertsHandler = async (incidentId: string) => {
    const apiUrl = getApiURL();
    const response = await fetch(`${apiUrl}/incidents/${incidentId}/alerts`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${session?.accessToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(alerts.map(({ event_id }) => event_id)),
    });
    if (response.ok) {
      handleSuccess();
      await mutate();
      toast.success("Alerts associated with incident successfully");
    } else {
      toast.error(
        "Failed to associated alerts with incident, please contact us if this issue persists."
      );
    }
  };

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
  if (!alerts) return null;

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title="Choose Incident"
      className="w-[600px]"
    >
      <div className="relative bg-white p-6 rounded-lg">
        {isLoading ? (
          <Loading />
        ) : createIncident ? (
          <CreateOrUpdateIncident
            incidentToEdit={null}
            createCallback={onIncidentCreated}
            exitCallback={hideCreateIncidentForm}
          />
        ) : incidents && incidents.items.length > 0 ? (
          <div className="h-full justify-center">
            <Select
              className="my-2.5"
              placeholder={`Select incident`}
              value={selectedIncident}
              onValueChange={(value) => setSelectedIncident(value)}
            >
              {
                incidents.items?.map((incident) => {
                  return (
                    <SelectItem key={incident.id} value={incident.id}>
                      {incident.name}
                    </SelectItem>
                  );
                })!
              }
            </Select>
            <Divider />
            <div className="flex items-center justify-between gap-6">
              <Button
                className="flex-1"
                color="orange"
                onClick={handleAssociateAlerts}
                disabled={selectedIncident === null}
              >
                Associate {alerts.length} alert{alerts.length > 1 ? "s" : ""}
              </Button>

              <Button
                className="flex-1"
                color="green"
                onClick={showCreateIncidentForm}
              >
                Create a new incident
              </Button>
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center gap-y-8 h-full">
            <div className="text-center space-y-3">
              <Title className="text-2xl">No Incidents Yet</Title>
            </div>

            <div className="flex items-center justify-between w-full gap-6">
              <Button
                className="flex-1"
                color="orange"
                onClick={() => router.push("/incidents")}
              >
                Incidents page
              </Button>

              <Button
                className="flex-1"
                color="green"
                onClick={showCreateIncidentForm}
              >
                Create a new incident
              </Button>
            </div>
          </div>
        )}
      </div>
    </Modal>
  );
};

export default AlertAssociateIncidentModal;
