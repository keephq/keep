import { Button, Title, Subtitle } from "@tremor/react";
import Modal from "@/components/ui/Modal";
import { IncidentDto, Status } from "./models";
import { useApiUrl } from "utils/hooks/useConfig";
import { useSession } from "next-auth/react";
import { toast } from "react-toastify";
import {
  CheckCircleIcon,
  ExclamationCircleIcon,
  PauseIcon,
} from "@heroicons/react/24/outline";

const statusIcons = {
  [Status.Firing]: <ExclamationCircleIcon className="w-4 h-4 mr-2" />,
  [Status.Resolved]: <CheckCircleIcon className="w-4 h-4 mr-2" />,
  [Status.Acknowledged]: <PauseIcon className="w-4 h-4 mr-2" />,
};

interface Props {
  sourceIncidents: IncidentDto[];
  destinationIncident: IncidentDto;
  mutate: () => void;
  handleClose: () => void;
}

export default function IncidentMergeModal({
  sourceIncidents,
  destinationIncident,
  mutate,
  handleClose,
}: Props) {
  const { data: session } = useSession();
  const apiUrl = useApiUrl();

  const handleMerge = async () => {
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
        handleClose();
        await mutate();
      } else {
        toast.error("Failed to merge incidents.");
      }
    } catch (error) {
      toast.error("An error occurred while merging incidents.");
    }
  };

  return (
    <Modal onClose={handleClose} isOpen={true}>
      <div className="flex flex-col gap-5">
        <div>
          <Title>Merge Incidents</Title>
          <Subtitle className="flex items-center">
            Alerts from the following incidents will be merged into the selected
            incident
          </Subtitle>
        </div>
        <div>
          <div className="mb-1">
            <span className="font-bold">Source Incidents</span>
          </div>
          <div className="flex flex-col gap-2">
            {sourceIncidents.map((incident) => (
              <div key={incident.id} className="flex items-center">
                <div className="w-4 h-4 mr-2">
                  {statusIcons[incident.status]}
                </div>
                <div className="flex-1">
                  <div className="text-pretty">
                    {incident.user_generated_name}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
        <div>
          <div className="mb-1">
            <span className="font-bold">Destination Incident</span>
          </div>
          <div className="flex items-center">
            <div className="w-4 h-4 mr-2">
              {statusIcons[destinationIncident.status]}
            </div>
            <div className="flex-1">
              <div className="text-pretty">
                {destinationIncident.user_generated_name}
              </div>
            </div>
          </div>
        </div>
      </div>
      <div className="flex justify-end mt-4 gap-2">
        <Button onClick={handleClose} color="orange" variant="secondary">
          Cancel
        </Button>
        <Button onClick={handleMerge} color="orange">
          Confirm merge
        </Button>
      </div>
    </Modal>
  );
}
