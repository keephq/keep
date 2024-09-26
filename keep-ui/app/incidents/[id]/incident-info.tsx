import { Button, Icon, Title } from "@tremor/react";
import { IncidentDto } from "../models";
import CreateOrUpdateIncident from "../create-or-update-incident";
import Modal from "@/components/ui/Modal";
import React, { useState } from "react";
import { MdBlock, MdDone, MdModeEdit } from "react-icons/md";
import { useIncident } from "../../../utils/hooks/useIncidents";
import {
  deleteIncident,
  handleConfirmPredictedIncident,
} from "../incident-candidate-actions";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { format } from "date-fns";
import { ArrowUturnLeftIcon } from "@heroicons/react/24/outline";

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

  const formatString = "dd, MMM yyyy - HH:mm.ss 'UTC'";
  const summary = incident.user_summary || incident.generated_summary;

  return (
    <div className="flex h-full flex-col justify-between">
      <div className="flex flex-col gap-2">
        <div className="flex justify-between text-sm">
          <Title className="">
            {incident.is_confirmed ? "⚔️ " : "Possible "}Incident
          </Title>
          {incident.is_confirmed && (
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
          )}
          {!incident.is_confirmed && (
            <div className="space-x-1 flex flex-row items-center justify-center">
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
                  handleConfirmPredictedIncident({
                    incidentId: incident.id!,
                    mutate,
                    session,
                  });
                }}
              >
                Confirm
              </Button>
              <Button
                color="red"
                size="xs"
                variant="secondary"
                tooltip={"Discard"}
                icon={MdBlock}
                onClick={async (e: React.MouseEvent) => {
                  e.preventDefault();
                  e.stopPropagation();
                  const success = await deleteIncident({
                    incidentId: incident.id!,
                    mutate,
                    session,
                  });
                  if (success) {
                    router.push("/incidents");
                  }
                }}
              />
            </div>
          )}
        </div>
        <div className="prose-2xl flex gap-2 items-start">
          <Icon
            icon={ArrowUturnLeftIcon}
            tooltip="Go Back"
            variant="shadow"
            className="cursor-pointer"
            onClick={() => router.back()}
          />
          <span>
            {incident.user_generated_name || incident.ai_generated_name}
          </span>
        </div>
        <div>
          <h3 className="text-gray-500 text-sm">Summary</h3>
          {summary ? <p>{summary}</p> : <p>No summary yet</p>}
        </div>
        <div className="flex gap-4">
          {!!incident.start_time && (
            <div>
              <h3 className="text-gray-500 text-sm">Started at</h3>
              <p className="">
                {format(new Date(incident.start_time), formatString)}
              </p>
            </div>
          )}
          {!!incident.last_seen_time && (
            <div>
              <h3 className="text-gray-500 text-sm">Last seen at</h3>
              <p>{format(new Date(incident.last_seen_time), formatString)}</p>
            </div>
          )}
        </div>
        <div>
          {!!incident.rule_fingerprint && (
            <>
              <h3 className="text-sm text-gray-500">Group by value</h3>
              <p>{incident.rule_fingerprint}</p>
            </>
          )}
        </div>
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
