"use client";
import { Card, Title, Subtitle, Button, Badge } from "@tremor/react";
import Loading from "app/loading";
import { useState } from "react";
import { IncidentDto } from "./models";
import CreateOrUpdateIncident from "./create-or-update-incident";
import IncidentsTable from "./incidents-table";
import { useIncidents, usePollIncidents } from "utils/hooks/useIncidents";
import { IncidentPlaceholder } from "./IncidentPlaceholder";
import Modal from "@/components/ui/Modal";
import { PlusCircleIcon } from "@heroicons/react/24/outline";
import PredictedIncidentsTable from "./predicted-incidents-table";
import {SortingState} from "@tanstack/react-table";
import {IncidentTableFilters} from "./incident-table-filters";
import {useIncidentFilterContext} from "./incident-table-filters-context";

interface Pagination {
  limit: number;
  offset: number;
}

interface Filters {
  status: string[],
  severity: string[],
  assignees: string[]
  sources: string[],
  affected_services: string[],
}

export default function Incident() {
  const [incidentsPagination, setIncidentsPagination] = useState<Pagination>({
    limit: 20,
    offset: 0,
  });

  const [incidentsSorting, setIncidentsSorting] = useState<SortingState>([
    { id: "creation_time", desc: true },
  ]);

  const {
    statuses,
    severities,
    assignees,
    services,
    sources,
  } = useIncidentFilterContext()

  const filters: Filters = {
    status: statuses,
    severity: severities,
    assignees: assignees,
    affected_services: services,
    sources: sources,
  }

  const {
    data: incidents,
    isLoading,
    mutate: mutateIncidents,
  } = useIncidents(
    true, incidentsPagination.limit, incidentsPagination.offset, incidentsSorting[0], filters);
  const {
    data: predictedIncidents,
    isLoading: isPredictedLoading,
    mutate: mutatePredictedIncidents,
  } = useIncidents(false);
  usePollIncidents(mutateIncidents);

  const [incidentToEdit, setIncidentToEdit] = useState<IncidentDto | null>(
    null
  );

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
      <div className="flex-grow min-w-0">
        {!isPredictedLoading &&
        predictedIncidents &&
        predictedIncidents.items.length > 0 ? (
          <Card className="mt-10 mb-10 flex-grow">
            <Title>Incident Predictions</Title>
            <Subtitle>
              Possible problems predicted by Keep AI & Correlation Rules{" "}
              <Badge color="orange">Beta</Badge>
            </Subtitle>
            <PredictedIncidentsTable
              incidents={predictedIncidents}
              mutate={async () => {
                await mutatePredictedIncidents();
                await mutateIncidents();
              }}
              editCallback={handleStartEdit}
            />
          </Card>
        ) : null}


        {isLoading ? (
          <Loading />
        ) : (
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

              <IncidentTableFilters />

              {incidents && incidents.items.length > 0 ?
                <IncidentsTable
                  incidents={incidents}
                  mutate={mutateIncidents}
                  setPagination={setIncidentsPagination}
                  sorting={incidentsSorting}
                  setSorting={setIncidentsSorting}
                  editCallback={handleStartEdit}
                /> :
                <IncidentPlaceholder setIsFormOpen={setIsFormOpen} />
              }
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
          exitCallback={handleFinishEdit}
        />
      </Modal>
    </div>
  );
}
