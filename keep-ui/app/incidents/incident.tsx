"use client";
import { Badge, Card } from "@tremor/react";
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
    <Card className="flex flex-col items-center justify-center gap-y-8 h-full">
      <Badge
        color="orange"
        size="xs"
        tooltip="Slack us if something isn't working properly :)"
        className="absolute top-[-10px] left-[-10px]"
      >
        Beta
      </Badge>
      <div className="flex divide-x p-2 h-full">
        <div className="pl-2.5">
          {isLoading ? (
            <Loading />
          ) : incidents && incidents.length > 0 ? (
            <div className="h-full justify-top">
                <IncidentsTable
                  incidents={incidents}
                  editCallback={handleStartEdit}
                />
            </div>
          ) : (
            <IncidentPlaceholder setIsFormOpen={setIsFormOpen}/>
          )}
        </div>
      </div>
      <Modal
        isOpen={isFormOpen}
        onClose={handleCloseForm}
        className="w-[600px]"
        title="Add Incident"
      >
          <CreateOrUpdateIncident incidentToEdit={incidentToEdit} editCallback={handleFinishEdit}/>
      </Modal>
    </Card>
  );
}
