import { Button, Title } from "@tremor/react";
import { IncidentDto } from "../model";
import CreateOrUpdateIncident from "../create-or-update-incident";
import Modal from "@/components/ui/Modal";
import React, { useState } from "react";
import { MdModeEdit } from "react-icons/md";
import { useIncident } from "../../../utils/hooks/useIncidents";
// import { RiSparkling2Line } from "react-icons/ri";

interface Props {
  incident: IncidentDto;
}

export default function IncidentInformation({ incident }: Props) {
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
          <Title className="">⚔️ Incident Information</Title>
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
        </div>
        <div className="prose-2xl">{incident.name}</div>
        <p>Description: {incident.description}</p>
        <p>Started at: {incident.start_time?.toString() ?? "N/A"}</p>
        {/* <Callout
          title="AI Summary"
          color="gray"
          icon={RiSparkling2Line}
          className="mt-10 mb-10"
        >
          Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do
          eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad
          minim veniam, quis nostrud exercitation ullamco laboris nisi ut
          aliquip ex ea commodo consequat. Duis aute irure dolor in
          reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla
          pariatur. Excepteur sint occaecat cupidatat non proident, sunt in
          culpa qui officia deserunt mollit anim id est laborum.
        </Callout> */}
      </div>
      <Modal
        isOpen={isFormOpen}
        onClose={handleCloseForm}
        className="w-[600px]"
        title="Edit Incident"
      >
        <CreateOrUpdateIncident
          incidentToEdit={incident}
          editCallback={handleFinishEdit}
        />
      </Modal>
    </div>
  );
}
