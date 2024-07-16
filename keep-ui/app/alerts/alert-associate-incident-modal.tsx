import React, {FormEvent, useState} from "react";
import { useSession } from "next-auth/react";
import { AlertDto } from "./models";
import Modal from "@/components/ui/Modal";
import { useIncidents } from "../../utils/hooks/useIncidents";
import Loading from "../loading";
import {Button, Divider, Select, SelectItem, Title} from "@tremor/react";
import {useRouter} from "next/navigation";
import {getApiURL} from "../../utils/apiUrl";
import {toast} from "react-toastify";

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

  const { data: incidents, isLoading, mutate } = useIncidents();
  const [selectedIncident, setSelectedIncident] = useState<string | null>(null);
  // get the token
  const { data: session } = useSession();
  const router = useRouter();
  // if this modal should not be open, do nothing
  if (!alerts) return null;
  const handleAssociateAlerts = async (e: FormEvent) => {
    e.preventDefault();
    const apiUrl = getApiURL();
    const response = await fetch(
      `${apiUrl}/incidents/${selectedIncident}/alerts`,
      {
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
  }


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
          ) : incidents && incidents.length > 0 ? (
            <div className="h-full justify-center">
              <Select
                className="my-2.5"
                placeholder={`Select incident`}
                onValueChange={(value) => setSelectedIncident(value)}
              >
                {
                  incidents?.map((incident) => {

                    return (
                      <SelectItem
                        key={incident.id}
                        value={incident.id}
                      >
                        {incident.name}
                      </SelectItem>
                    );
                  })!
                }
              </Select>
              <Divider />
              <div className="right">
                <Button
                  color="orange"
                  onClick={handleAssociateAlerts}
                  disabled={selectedIncident === null}
                >
                  Associate {alerts.length} alert{alerts.length > 1 ? "s" : ""}
                </Button>
              </div>

            </div>
          ) : (
            <div className="flex flex-col items-center justify-center gap-y-8 h-full">
              <div className="text-center space-y-3">
                <Title className="text-2xl">No Incidents Yet</Title>
              </div>
              <Button
                className="mb-10"
                color="orange"
                onClick={() => router.push("/incidents")}
              >
                Register Incident
              </Button>
            </div>
          )}
      </div>
    </Modal>
  );
};

export default AlertAssociateIncidentModal;
