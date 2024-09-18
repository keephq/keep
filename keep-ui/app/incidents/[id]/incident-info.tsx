
import {Button, Title} from "@tremor/react";
import { IncidentDto } from "../models";
import CreateOrUpdateIncident from "../create-or-update-incident";
import Modal from "@/components/ui/Modal";
import React, {useState} from "react";
import {MdBlock, MdDone, MdModeEdit} from "react-icons/md";
import {useIncident} from "../../../utils/hooks/useIncidents";
import {deleteIncident, handleConfirmPredictedIncident} from "../incident-candidate-actions";
import {useSession} from "next-auth/react";
import {useRouter} from "next/navigation";
// import { RiSparkling2Line } from "react-icons/ri";

interface Props {
  incident: IncidentDto;
}

export default function IncidentInformation({ incident }: Props) {
  const router = useRouter();
  const { data: session } = useSession();
  const { mutate } = useIncident(incident.id);
  const [isFormOpen, setIsFormOpen] = useState<boolean>(false);

  const handleCloseForm = () => {
    setIsFormOpen(false);
  };

  const handleStartEdit = () => {
    setIsFormOpen(true);
  };

  const handleFinishEdit = () => {
    setIsFormOpen(false);
    mutate();
  };

  return (
    <div className="flex h-full flex-col justify-between">
      <div>
        <div className="flex justify-between mb-2.5">
          <Title className="">{incident.is_confirmed ? "⚔️ " : "Possible "}Incident Information</Title>
          {incident.is_confirmed &&
            <Button
              color="orange"
              size="xs"
              variant="secondary"
              icon={MdModeEdit}
              onClick={(e: React.MouseEvent) => {
                e.preventDefault();
                e.stopPropagation();
                handleStartEdit();
              }}
            />
          }
          {!incident.is_confirmed &&
            <div className={"space-x-1 flex flex-row items-center justify-center"}>
              <Button
                color="orange"
                size="xs"
                tooltip="Confirm incident"
                variant="secondary"
                title="Confirm"
                icon={MdDone}
                onClick={(e: React.MouseEvent) => {
                  e.preventDefault();
                  e.stopPropagation();
                  handleConfirmPredictedIncident({incidentId: incident.id!, mutate, session});
                }}
              >Confirm</Button>
              <Button
                color="red"
                size="xs"
                variant="secondary"
                tooltip={"Discard"}
                icon={MdBlock}
                onClick={async (e: React.MouseEvent) => {
                  e.preventDefault();
                  e.stopPropagation();
                  const success = await deleteIncident({incidentId: incident.id!, mutate, session});
                  if (success) {
                    router.push("/incidents");
                  }
                }}
              />
            </div>
          }
        </div>
        <div className="prose-2xl">{incident.user_generated_name || incident.ai_generated_name}</div>
        <p>Summary: {incident.user_summary || incident.generated_summary}</p>
        {!!incident.start_time && <p>Started at: {new Date(incident.start_time + "Z").toLocaleString()}</p>}
        {!!incident.last_seen_time && <p>Last seen at: {new Date(incident.last_seen_time + "Z").toLocaleString()}</p>}
        {!!incident.rule_fingerprint && <p>Group by value: {incident.rule_fingerprint}</p>}

      </div>
      <Modal
        isOpen={isFormOpen}
        onClose={handleCloseForm}
        className="w-[600px]"
        title="Edit Incident"
      >
        <CreateOrUpdateIncident
          incidentToEdit={incident}
          exitCallback={handleFinishEdit}
        />
      </Modal>
    </div>
  );
}
