"use client";
import { Card, Title, Subtitle, Button, Badge } from "@tremor/react";
import Loading from "@/app/(keep)/loading";
import React, { useState } from "react";
import type {
  IncidentDto,
  PaginatedIncidentsDto,
} from "@/entities/incidents/model";
import { CreateOrUpdateIncidentForm } from "@/features/create-or-update-incident";
import IncidentsTable from "./incidents-table";
import { useIncidents, usePollIncidents } from "@/utils/hooks/useIncidents";
import { IncidentListPlaceholder } from "./incident-list-placeholder";
import Modal from "@/components/ui/Modal";
import { PlusCircleIcon } from "@heroicons/react/24/outline";
import PredictedIncidentsTable from "@/app/(keep)/incidents/predicted-incidents-table";
import { SortingState } from "@tanstack/react-table";
import { IncidentListError } from "@/features/incident-list/ui/incident-list-error";
import { InitialFacetsData } from "@/features/filter/api";
import { FacetsPanelServerSide } from "@/features/filter/facet-panel-server-side";

interface Pagination {
  limit: number;
  offset: number;
}

export function IncidentList({
  initialData,
  initialFacetsData,
}: {
  initialData?: PaginatedIncidentsDto;
  initialFacetsData?: InitialFacetsData;
}) {
  const [incidentsPagination, setIncidentsPagination] = useState<Pagination>({
    limit: 20,
    offset: 0,
  });

  const [incidentsSorting, setIncidentsSorting] = useState<SortingState>([
    { id: "creation_time", desc: true },
  ]);

  const [filterCel, setFilterCel] = useState<string>('');

  const {
    data: incidents,
    isLoading,
    mutate: mutateIncidents,
    error: incidentsError,
  } = useIncidents(
    true,
    incidentsPagination.limit,
    incidentsPagination.offset,
    incidentsSorting[0],
    filterCel,
    {
      revalidateOnFocus: false,
      revalidateOnMount: !initialData,
      fallbackData: initialData,
    }
  );

  const { data: predictedIncidents, isLoading: isPredictedLoading } =
    useIncidents(false);
  usePollIncidents(mutateIncidents);

  const [incidentToEdit, setIncidentToEdit] = useState<IncidentDto | null>(
    null
  );

  const [isFormOpen, setIsFormOpen] = useState<boolean>(false);

  const handleCloseForm = () => {
    setIsFormOpen(false);
    setIncidentToEdit(null);
  };

  const handleStartEdit = (incident: IncidentDto) => {
    setIncidentToEdit(incident);
    setIsFormOpen(true);
  };

  const handleFinishEdit = () => {
    setIncidentToEdit(null);
    setIsFormOpen(false);
  };

  function renderIncidents() {
    if (incidentsError) {
      return <IncidentListError incidentError={incidentsError} />;
    }

    if (incidents && (incidents.items.length > 0)) {
      return (
        <IncidentsTable
          incidents={incidents}
          setPagination={setIncidentsPagination}
          sorting={incidentsSorting}
          setSorting={setIncidentsSorting}
          editCallback={handleStartEdit}
        />
      );
    }

    // This is shown on the cold page load. FIXME
    return (
      <Card className="flex-grow">
        <IncidentListPlaceholder setIsFormOpen={setIsFormOpen} />
      </Card>
    );
  }

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
              editCallback={handleStartEdit}
            />
          </Card>
        ) : null}

        <div className="h-full flex flex-col gap-5">
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
          <div>
            {isLoading && (
              <Loading />
            )}
            
              <div className="flex flex-row gap-5">
                <FacetsPanelServerSide
                  panelId={"incidents"}
                  initialFacetsData={initialFacetsData}
                  className="mt-14"
                  onCelChange={(cel) => setFilterCel(cel)}
                />
                <div className="flex flex-col gap-5 flex-1">
                  {!isLoading && (
                    renderIncidents()
                  )}
                </div>
              </div>
          </div>
        </div>
      </div>
      <Modal
        isOpen={isFormOpen}
        onClose={handleCloseForm}
        className="w-[600px]"
        title="Add Incident"
      >
        <CreateOrUpdateIncidentForm
          incidentToEdit={incidentToEdit}
          exitCallback={handleFinishEdit}
        />
      </Modal>
    </div>
  );
}
