"use client";
import { Card, Title, Subtitle, Button, Badge } from "@tremor/react";
import React, { useCallback, useEffect, useMemo, useState } from "react";
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
import Image from "next/image";
import { Icon } from "@tremor/react";
import { SeverityBorderIcon, UISeverity } from "@/shared/ui";
import { BellIcon, BellSlashIcon } from "@heroicons/react/24/outline";
import { UserStatefulAvatar } from "@/entities/users/ui";
import { getStatusIcon, getStatusColor } from "@/shared/lib/status-utils";
import { useUser } from "@/entities/users/model/useUser";
import {
  reverseSeverityMapping,
  severityMapping,
} from "@/entities/alerts/model";
import { IncidentsNotFoundPlaceholder } from "./incidents-not-found";
import { v4 as uuidV4 } from "uuid";
import { FacetsConfig } from "@/features/filter/models";

const AssigneeLabel = ({ email }: { email: string }) => {
  const user = useUser(email);
  return user ? user.name : email;
};

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

  const [filterCel, setFilterCel] = useState<string>("");

  const {
    data: incidents,
    isLoading,
    mutate: mutateIncidents,
    error: incidentsError,
  } = useIncidents(
    true,
    null,
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
    useIncidents(false, true);
  const { incidentChangeToken } = usePollIncidents(mutateIncidents);

  const [incidentToEdit, setIncidentToEdit] = useState<IncidentDto | null>(
    null
  );

  const [clearFiltersToken, setClearFiltersToken] = useState<string | null>(
    null
  );
  const [filterRevalidationToken, setFilterRevalidationToken] = useState<
    string | null
  >(null);
  const [isFormOpen, setIsFormOpen] = useState<boolean>(false);

  useEffect(() => {
    setFilterRevalidationToken(incidentChangeToken);
  }, [incidentChangeToken]);

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

  const facetsConfig: FacetsConfig = useMemo(() => {
    return {
      ["Severity"]: {
        canHitEmptyState: false,
        renderOptionLabel: (facetOption) => {
          const label =
            severityMapping[Number(facetOption.display_name)] ||
            facetOption.display_name;
          return <span className="capitalize">{label}</span>;
        },
        renderOptionIcon: (facetOption) => (
          <SeverityBorderIcon
            severity={
              (severityMapping[Number(facetOption.display_name)] ||
                facetOption.display_name) as UISeverity
            }
          />
        ),
        sortCallback: (facetOption) =>
          reverseSeverityMapping[facetOption.value] || 100, // if status is not in the mapping, it should be at the end
      },
      ["Status"]: {
        renderOptionIcon: (facetOption) => (
          <Icon
            icon={getStatusIcon(facetOption.display_name)}
            size="sm"
            color={getStatusColor(facetOption.display_name)}
            className="!p-0"
          />
        ),
      },
      ["Source"]: {
        renderOptionIcon: (facetOption) => {
          if (facetOption.display_name === "None") {
            return;
          }

          return (
            <Image
              className="inline-block"
              alt={facetOption.display_name}
              height={16}
              width={16}
              title={facetOption.display_name}
              src={
                facetOption.display_name.includes("@")
                  ? "/icons/mailgun-icon.png"
                  : `/icons/${facetOption.display_name}-icon.png`
              }
            />
          );
        },
      },
      ["Assignee"]: {
        renderOptionIcon: (facetOption) => (
          <UserStatefulAvatar email={facetOption.display_name} size="xs" />
        ),
        renderOptionLabel: (facetOption) => {
          if (!facetOption.display_name) {
            return "Not assigned";
          }
          return <AssigneeLabel email={facetOption.display_name} />;
        },
      },
      ["Dismissed"]: {
        renderOptionLabel: (facetOption) =>
          facetOption.display_name === "true" ? "Dismissed" : "Not dismissed",
        renderOptionIcon: (facetOption) => (
          <Icon
            icon={
              facetOption.display_name === "true" ? BellSlashIcon : BellIcon
            }
            size="sm"
            className="text-gray-600 !p-0"
          />
        ),
      },
    };
  }, []);

  function renderIncidents() {
    if (incidents && incidents.items.length > 0) {
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

    if (filterCel && incidents?.items.length === 0) {
      return (
        <Card className="flex-grow ">
          <IncidentsNotFoundPlaceholder
            onClearFilters={() => setClearFiltersToken(uuidV4())}
          />
        </Card>
      );
    }

    // This is shown on the cold page load. FIXME
    return (
      <Card className="flex-grow">
        <IncidentListPlaceholder setIsFormOpen={setIsFormOpen} />
      </Card>
    );
  }

  const uncheckedFacetOptionsByDefault: Record<string, string[]> = {
    Status: ["resolved", "deleted"],
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
            {incidentsError ? (
              <IncidentListError incidentError={incidentsError} />
            ) : null}
            {incidentsError ? null : (
              <div className="flex flex-row gap-5">
                <FacetsPanelServerSide
                  className="mt-14"
                  entityName={"incidents"}
                  facetsConfig={facetsConfig}
                  usePropertyPathsSuggestions={true}
                  clearFiltersToken={clearFiltersToken}
                  initialFacetsData={initialFacetsData}
                  uncheckedByDefaultOptionValues={
                    uncheckedFacetOptionsByDefault
                  }
                  onCelChange={(cel) => setFilterCel(cel)}
                  revalidationToken={filterRevalidationToken}
                />
                <div className="flex flex-col gap-5 flex-1 min-w-0">
                  {renderIncidents()}
                </div>
              </div>
            )}
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
