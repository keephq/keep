"use client";
import { Card, Title, Subtitle, Button } from "@tremor/react";
import Loading from "app/loading";
import { useState } from "react";
import { IncidentDto } from "./model";
import CreateOrUpdateIncident from "./create-or-update-incident";
import IncidentsTable from "./incidents-table";
import { useIncidents, usePollIncidents } from "utils/hooks/useIncidents";
import { IncidentPlaceholder } from "./IncidentPlaceholder";
import Modal from "@/components/ui/Modal";
import { PlusCircleIcon } from "@heroicons/react/24/outline";
import PredictedIncidentsTable from "./predicted-incidents-table";

interface Pagination {
  limit: number;
  offset: number;
}

export default function Incident() {
  const [incidentsPagination, setIncidentsPagination] = useState<Pagination>({
    limit: 20,
    offset: 0,
  });

  const { data: incidents, isLoading,
    mutate: mutateIncidents} = useIncidents(
      true,
      incidentsPagination.limit,
      incidentsPagination.offset
  );
  const { data: predictedIncidents, isLoading: isPredictedLoading,
    mutate: mutatePredictedIncidents } = useIncidents(false);
  usePollIncidents(mutateIncidents);

  const [incidentToEdit, setIncidentToEdit] =
    useState<IncidentDto | null>(null);

  const [isFormOpen, setIsFormOpen] = useState<boolean>(false);

  const handleCloseForm = () => {
    setIsFormOpen(false);
  };

  const handleStartEdit = (incident: IncidentDto) => {
    setIncidentToEdit(incident);
    setIsFormOpen(true);
  };

  const handleFinishEdit = () => {
    setIncidentToEdit(null);
    setIsFormOpen(false);
  };

  return (
    <div className="flex h-full w-full">
      <div className="flex-grow overflow-auto p-2.5">
        {!isPredictedLoading && predictedIncidents && predictedIncidents.items.length > 0 ?
          <Card className="mt-10 mb-10 flex-grow">
            <Title>Incident Predictions</Title>
            <Subtitle>Possible problems predicted by Keep AI <Badge color="orange">Beta</Badge></Subtitle>
            <PredictedIncidentsTable
              incidents={predictedIncidents}
              mutate={async () => {
                await mutatePredictedIncidents();
                await mutateIncidents();
              }}
              editCallback={handleStartEdit}
            />
          </Card>
        : null
        }

        {isLoading ? (
          <Loading />
        ) : incidents && incidents.items.length > 0 ? (
          <div className="h-full flex flex-col">
            <div className="flex justify-between items-center">
              <div>
                <Title>Incidents</Title>
                <Subtitle>Manage your incidents</Subtitle>
              </div>
              <div>
                <Button
                  color="orange"
                  size="md"
                  icon={PlusCircleIcon}
                  onClick={() => setIsFormOpen(true)}
                >
                  Create Incident
                </Button>
              </div>
            </div>
            <Card className="mt-10 flex-grow">
              <IncidentsTable
                incidents={incidents}
                mutate={mutateIncidents}
                setPagination={setIncidentsPagination}
                editCallback={handleStartEdit}
              />
            </Card>
          </div>
        ) : (
          <div className="h-full flex">
            <Card className="flex-grow flex items-center justify-center">
              <IncidentPlaceholder setIsFormOpen={setIsFormOpen} />
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
        <CreateOrUpdateIncident
          incidentToEdit={incidentToEdit}
          editCallback={handleFinishEdit}
        />
      </Modal>
    </div>
  );
}
