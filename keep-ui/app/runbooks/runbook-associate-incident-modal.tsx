import Modal from "@/components/ui/Modal";
import { Button, Divider, SelectItem, Title } from "@tremor/react";
import Select from "@/components/ui/Select";
import CreateOrUpdateIncident from "app/incidents/create-or-update-incident";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { toast } from "react-toastify";
import { getApiURL } from "../../utils/apiUrl";
import { useIncidents, usePollIncidents } from "../../utils/hooks/useIncidents";
import Loading from "../loading";
import { RunbookDto } from "./models";

interface AlertAssociateIncidentModalProps {
  isOpen: boolean;
  handleSuccess: () => void;
  handleClose: () => void;
  runbooks: Array<RunbookDto>;
}

const RunbookAssociateIncidentModal = ({
  isOpen,
  handleSuccess,
  handleClose,
  runbooks,
}: AlertAssociateIncidentModalProps) => {
  const [createIncident, setCreateIncident] = useState(false);

  const { data: incidents, isLoading, mutate } = useIncidents(true, 100);
  usePollIncidents(mutate);

  const [selectedIncident, setSelectedIncident] = useState<
    string | undefined
  >();
  // get the token
  const { data: session } = useSession();
  const router = useRouter();
  console.log("Associating runbooks is outside", runbooks.map(({ id }) => id));

  const associateRunbooksHandler = async (incidentId: string) => {
    const apiUrl = getApiURL();
    console.log("Associating runbooks with incident", incidentId);
    console.log("Associating runbooks is", runbooks.map(({ id }) => id));
    console.log("Associating session?.accessToken", session?.accessToken);
    
    const response = await fetch(`${apiUrl}/incidents/${incidentId}/runbooks`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${session?.accessToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(runbooks.map(({ id }) => id)),
    });
    if (response.ok) {
      handleSuccess();
      await mutate();
      toast.success("Runbooks associated with incident successfully");
    } else {
      toast.error(
        "Failed to associated runbooks with incident, please contact us if this issue persists."
      );
    }
  };

  const handleAssociateRunbooks = (e: FormEvent) => {
    e.preventDefault();
    if (selectedIncident) associateRunbooksHandler(selectedIncident);
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
      associateRunbooksHandler(incidentId);
    },
    [associateRunbooksHandler, handleClose, hideCreateIncidentForm]
  );

  // reset modal state after closing
  useEffect(() => {
    if (!isOpen) {
      hideCreateIncidentForm();
      setSelectedIncident(undefined);
    }
  }, [hideCreateIncidentForm, isOpen]);

  // if this modal should not be open, do nothing
  if (!runbooks) return null;

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
              placeholder="Select incident"
              value={
                selectedIncident
                  ? {
                      value: selectedIncident,
                      label:
                        incidents.items.find(
                          (incident) => incident.id === selectedIncident
                        )?.user_generated_name ||
                        incidents.items.find(
                          (incident) => incident.id === selectedIncident
                        )?.ai_generated_name ||
                        "",
                    }
                  : null
              }
              onChange={(selectedOption) =>
                setSelectedIncident(selectedOption?.value)
              }
              options={incidents.items?.map((incident) => ({
                value: incident.id,
                label:
                  incident.user_generated_name ||
                  incident.ai_generated_name ||
                  "",
              }))}
            />
            <Divider />
            <div className="flex items-center justify-between gap-6">
              <Button
                className="flex-1"
                color="orange"
                onClick={handleAssociateRunbooks}
                disabled={selectedIncident === null}
              >
                Associate {runbooks.length} Runbook{runbooks.length > 1 ? "s" : ""}
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

export default RunbookAssociateIncidentModal;
