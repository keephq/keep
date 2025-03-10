"use client";
import { Card, Title, Subtitle, Button, Badge } from "@tremor/react";
import React, { useEffect, useMemo, useState } from "react";
import type {
  IncidentDto,
  PaginatedIncidentsDto,
} from "@/entities/incidents/model";
import { CreateOrUpdateIncidentForm } from "@/features/create-or-update-incident";
import IncidentsTable from "./incidents-table";
import { useIncidents, usePollIncidents } from "@/utils/hooks/useIncidents";
import { IncidentListPlaceholder } from "./incident-list-placeholder";
import Modal from "@/components/ui/Modal";
import PredictedIncidentsTable from "@/app/(keep)/incidents/predicted-incidents-table";
import { SortingState } from "@tanstack/react-table";
import { IncidentListError } from "@/features/incident-list/ui/incident-list-error";
import { InitialFacetsData } from "@/features/filter/api";
import { FacetsPanelServerSide } from "@/features/filter/facet-panel-server-side";
import Image from "next/image";
import { Icon } from "@tremor/react";
import {
  PageSubtitle,
  PageTitle,
  SeverityBorderIcon,
  UISeverity,
} from "@/shared/ui";
import { BellIcon, BellSlashIcon } from "@heroicons/react/24/outline";
import { UserStatefulAvatar } from "@/entities/users/ui";
import { getStatusIcon, getStatusColor } from "@/shared/lib/status-utils";
import { useUser } from "@/entities/users/model/useUser";
import {
  reverseSeverityMapping,
  severityMapping,
} from "@/entities/alerts/model";
import {
  IncidentsNotFoundForFiltersPlaceholder,
  IncidentsNotFoundPlaceholder,
} from "./incidents-not-found";
import { v4 as uuidV4 } from "uuid";
import { FacetsConfig } from "@/features/filter/models";
import EnhancedDateRangePicker, {
  TimeFrame,
} from "@/components/ui/DateRangePicker";
import { PlusIcon } from "@heroicons/react/20/solid";
import {
  DEFAULT_INCIDENTS_CEL,
  DEFAULT_INCIDENTS_PAGE_SIZE,
  DEFAULT_INCIDENTS_SORTING,
  DEFAULT_INCIDENTS_UNCHECKED_OPTIONS,
} from "@/entities/incidents/model/models";

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
    limit: DEFAULT_INCIDENTS_PAGE_SIZE,
    offset: 0,
  });

  const [incidentsSorting, setIncidentsSorting] = useState<SortingState>([
    DEFAULT_INCIDENTS_SORTING,
  ]);

  const [filterCel, setFilterCel] = useState<string>("");
  const [dateRangeCel, setDateRangeCel] = useState<string>("");

  const [dateRange, setDateRange] = useState<TimeFrame>({
    start: null,
    end: null,
    paused: false,
  });

  const mainCelQuery = useMemo(() => {
    const filterArray = ["is_confirmed == true", dateRangeCel];
    return filterArray.filter(Boolean).join(" && ");
  }, [dateRangeCel]);

  const incidentsCelQuery = useMemo(() => {
    const filterArray = [mainCelQuery, filterCel];
    return filterArray.filter(Boolean).join(" && ");
  }, [filterCel, mainCelQuery]);

  // This is used to decide if the "No active incidents found" state should be shown
  const { data: defaultIncidents, mutate: refreshDefaultIncidents } =
    useIncidents(
      null,
      null,
      DEFAULT_INCIDENTS_PAGE_SIZE,
      0,
      DEFAULT_INCIDENTS_SORTING,
      DEFAULT_INCIDENTS_CEL,
      {
        revalidateOnFocus: false,
        revalidateOnMount: false,
        fallbackData: initialData,
      }
    );
  const isTrueEmptyState = defaultIncidents?.items.length === 0;

  const {
    data: incidents,
    isLoading,
    mutate: mutateIncidents,
    error: incidentsError,
  } = useIncidents(
    null,
    null,
    incidentsPagination.limit,
    incidentsPagination.offset,
    incidentsSorting[0],
    incidentsCelQuery,
    {
      revalidateOnFocus: false,
      revalidateOnMount: !initialData,
      fallbackData: initialData,
      onSuccess: () => {
        refreshDefaultIncidents();
      },
    }
  );

  const { data: predictedIncidents, isLoading: isPredictedLoading } =
    useIncidents(false, true);
  const { incidentChangeToken } = usePollIncidents(
    mutateIncidents,
    dateRange.paused
  );

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

  useEffect(() => {
    const filterArray: string[] = [];

    if (dateRange?.start) {
      filterArray.push(`creation_time >= '${dateRange.start.toISOString()}'`);
    }

    if (dateRange?.paused && dateRange?.end) {
      filterArray.push(`creation_time <= '${dateRange.end.toISOString()}'`);
    }

    setDateRangeCel(filterArray.filter(Boolean).join(" && "));
  }, [dateRange]);

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
        uncheckedByDefaultOptionValues: DEFAULT_INCIDENTS_UNCHECKED_OPTIONS,
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
      ["Linked incident"]: {
        sortCallback: (facetOption) =>
          facetOption.display_name == "1" ||
          facetOption.display_name.toLocaleLowerCase() == "true"
            ? 1
            : 0,
        renderOptionLabel: (facetOption) =>
          facetOption.display_name == "1" ||
          facetOption.display_name.toLocaleLowerCase() == "true"
            ? "Yes"
            : "No",
      },
    };
  }, []);

  const handleClearFilters = () => {
    setDateRange({
      start: null,
      end: null,
      paused: false,
    });
    setIncidentsPagination({
      limit: DEFAULT_INCIDENTS_PAGE_SIZE,
      offset: 0,
    });
    setClearFiltersToken(uuidV4());
  };

  function renderIncidents() {
    if (incidents && incidents.items.length > 0) {
      return (
        <IncidentsTable
          filterCel={mainCelQuery}
          incidents={incidents}
          setPagination={setIncidentsPagination}
          sorting={incidentsSorting}
          setSorting={setIncidentsSorting}
          editCallback={handleStartEdit}
        />
      );
    }

    if (isTrueEmptyState) {
      return <IncidentsNotFoundPlaceholder />;
    }

    if (mainCelQuery && incidents?.items.length === 0) {
      return (
        <IncidentsNotFoundForFiltersPlaceholder
          onClearFilters={handleClearFilters}
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

  const renderDateTimePicker = () => {
    return (
      <div className="flex justify-end">
        <EnhancedDateRangePicker
          timeFrame={dateRange}
          setTimeFrame={(timeFrame) => setDateRange(timeFrame)}
          timeframeRefreshInterval={20000}
          hasPlay={true}
          pausedByDefault={false}
          hasRewind={false}
          hasForward={false}
          hasZoomOut={false}
          enableYearNavigation
        />
      </div>
    );
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
              <PageTitle>Incidents</PageTitle>
              <PageSubtitle>Group alerts into incidents</PageSubtitle>
            </div>

            <div className="flex gap-2">
              {renderDateTimePicker()}
              <Button
                color="orange"
                size="md"
                icon={PlusIcon}
                variant="primary"
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
                  facetOptionsCel={mainCelQuery}
                  usePropertyPathsSuggestions={true}
                  clearFiltersToken={clearFiltersToken}
                  initialFacetsData={initialFacetsData}
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
