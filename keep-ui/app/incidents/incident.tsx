"use client";
import { Card, Title, Subtitle, Button, Badge } from "@tremor/react";
import { Loading } from "@/components/Loading";
import { useState } from "react";
import { IncidentDto, PaginatedIncidentsDto } from "./models";
import CreateOrUpdateIncident from "./create-or-update-incident";
import IncidentsTable from "./incidents-table";
import { useIncidents, usePollIncidents } from "utils/hooks/useIncidents";
import { IncidentPlaceholder } from "./IncidentPlaceholder";
import Modal from "@/components/ui/Modal";
import { PlusCircleIcon } from "@heroicons/react/24/outline";
import PredictedIncidentsTable from "./predicted-incidents-table";
import { SortingState } from "@tanstack/react-table";
import {
  defaultPagination,
  defaultSorting,
  Pagination,
} from "@/app/incidents/api";

type IncidentProps = {
  initialIncidents?: PaginatedIncidentsDto;
  initialPredictedIncidents?: PaginatedIncidentsDto;
};

export default function Incident({
  initialIncidents,
  initialPredictedIncidents,
}: IncidentProps) {
  const [incidentsPagination, setIncidentsPagination] =
    useState<Pagination>(defaultPagination);

  const [incidentsSorting, setIncidentsSorting] =
    useState<SortingState>(defaultSorting);

  const {
    data: incidents,
    isLoading,
    mutate: mutateIncidents,
  } = useIncidents(
    true,
    incidentsPagination.limit,
    incidentsPagination.offset,
    incidentsSorting[0],
    {
      revalidateOnFocus: false,
      fallbackData: initialIncidents,
    }
  );
  const {
    data: predictedIncidents,
    isLoading: isPredictedLoading,
    mutate: mutatePredictedIncidents,
  } = useIncidents(
    false,
    incidentsPagination.limit,
    incidentsPagination.offset,
    incidentsSorting[0],
    {
      revalidateOnFocus: false,
      fallbackData: initialPredictedIncidents,
    }
  );
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
                sorting={incidentsSorting}
                setSorting={setIncidentsSorting}
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
          exitCallback={handleFinishEdit}
        />
      </Modal>
    </div>
  );
}
