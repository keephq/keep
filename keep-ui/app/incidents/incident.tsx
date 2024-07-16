"use client";
import { Badge, Card, Title, Subtitle } from "@tremor/react";
import Loading from "app/loading";
import { useState } from "react";
import { IncidentDto } from "./model";
import CreateOrUpdateIncident from "./create-or-update-incident";
import IncidentsTable from "./incidents-table";
import { useIncidents } from "utils/hooks/useIncidents";
import { IncidentPlaceholder } from "./IncidentPlaceholder";
import Modal from "@/components/ui/Modal";

export default function Incident() {
  const { data: incidents, isLoading } = useIncidents();
  const [incidentToEdit, setIncidentToEdit] =
    useState<IncidentDto | null>(null);

  const [isFormOpen, setIsFormOpen] = useState<boolean>(false);

  const handleCloseForm = () => {
      setIsFormOpen(false);
  }

  const handleStartEdit = (incident: IncidentDto) => {
      setIncidentToEdit(incident);
      setIsFormOpen(true);
  }
  const handleFinishEdit = () => {
      setIncidentToEdit(null);
      setIsFormOpen(false);
  }

  return (
    <div className="flex h-full w-full">
      <div className="flex-grow overflow-auto p-2.5">
        {isLoading ? (
          <Loading />
        ) : incidents && incidents.length > 0 ? (
          <div className="h-full flex flex-col">
            <Title>Incidents</Title>
            <Subtitle>Manage your incidents</Subtitle>
            <Card className="mt-10 flex-grow">
              <IncidentsTable
                incidents={incidents}
                editCallback={handleStartEdit}
              />
            </Card>
          </div>
        ) : (
          <div className="h-full flex">
            <Card className="flex-grow flex items-center justify-center">
              <IncidentPlaceholder setIsFormOpen={setIsFormOpen}/>
            </Card>
          </div>
        )}
      </div>
      <Modal
        isOpen={isFormOpen}
        onClose={handleCloseForm}
        className="w-[600px]"
        title="Add Incident"
      >
        <CreateOrUpdateIncident incidentToEdit={incidentToEdit} editCallback={handleFinishEdit}/>
      </Modal>
    </div>
  );
}
