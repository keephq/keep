"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Button } from "@tremor/react";
import { ArrowUpOnSquareStackIcon } from "@heroicons/react/24/outline";
import {
  EmptyStateCard,
  ErrorComponent,
  KeepLoader,
  PageTitle,
} from "@/shared/ui";
import WorkflowsEmptyState from "./noworkflows";
import WorkflowTile from "./workflow-tile";
import {
  DEFAULT_WORKFLOWS_PAGINATION,
  DEFAULT_WORKFLOWS_QUERY,
  useWorkflowsV2,
  WorkflowsQuery,
} from "@/entities/workflows/model/useWorkflowsV2";
import { PageSubtitle } from "@/shared/ui/PageSubtitle";
import { PlusIcon } from "@heroicons/react/20/solid";
import { UserStatefulAvatar } from "@/entities/users/ui";
import { FacetsConfig } from "@/features/filter/models";
import {
  CheckCircleIcon,
  XCircleIcon,
  ExclamationCircleIcon,
  MagnifyingGlassIcon,
  FunnelIcon,
  ArrowPathIcon,
} from "@heroicons/react/24/outline";
import { useUser } from "@/entities/users/model/useUser";
import { Pagination, SearchInput } from "@/features/filter";
import { FacetsPanelServerSide } from "@/features/filter/facet-panel-server-side";
import { InitialFacetsData } from "@/features/filter/api";
import { v4 as uuidV4 } from "uuid";
import { PaginationState } from "@/features/filter/pagination";
import { CreateWorkflowModal } from "./create-workflow-modal";
import { UploadWorkflowsModal } from "./upload-workflows-modal";

const AssigneeLabel = ({ email }: { email: string }) => {
  const user = useUser(email);
  return user ? user.name : email;
};

export function ExistingWorkflowsState({
  initialFacetsData,
}: {
  initialFacetsData?: InitialFacetsData;
}) {
  const [isUploadWorkflowsModalOpen, setIsUploadWorkflowsModalOpen] =
    useState(false);
  const [isCreateWorkflowModalOpen, setIsCreateWorkflowModalOpen] =
    useState(false);
  const [clearFiltersToken, setClearFiltersToken] = useState<string | null>(
    null
  );
  const [filterCel, setFilterCel] = useState<string | null>(null);
  const [searchedValue, setSearchedValue] = useState<string | null>(null);
  const [paginationState, setPaginationState] = useState<PaginationState>(
    DEFAULT_WORKFLOWS_PAGINATION
  );
  const [workflowsQuery, setWorkflowsQuery] = useState<WorkflowsQuery>(
    DEFAULT_WORKFLOWS_QUERY
  );

  const searchCel = useMemo(() => {
    if (!searchedValue) {
      return;
    }

    return `name.contains("${searchedValue}") || description.contains("${searchedValue}")`;
  }, [searchedValue]);

  useEffect(() => {
    const celList = [searchCel, filterCel].filter((cel) => !!cel);
    const cel = celList.join(" && ");
    const query: WorkflowsQuery = {
      cel,
      limit: paginationState.limit,
      offset: paginationState.offset,
      sortBy: "created_at",
      sortDir: "desc",
    };

    setWorkflowsQuery(query);
  }, [searchCel, filterCel, paginationState]);

  // Only fetch data when the user is authenticated
  /**
    Redesign the workflow Card
      The workflow card needs execution records (currently limited to 15) for the graph. To achieve this, the following changes
      were made in the backend:
      1. Query Search Parameter: A new query search parameter called is_v2 has been added, which accepts a boolean
        (default is false).
      2. Grouped Workflow Executions: When a request is made with /workflows?is_v2=true, workflow executions are grouped
         by workflow.id.
      3. Response Updates: The response includes the following new keys and their respective information:
          -> last_executions: Used for the workflow execution graph.
          ->last_execution_started: Used for showing the start time of execution in real-time.
  **/

  const {
    workflows: filteredWorkflows,
    totalCount: filteredWorkflowsCount,
    error,
    isLoading: isFilteredWorkflowsLoading,
  } = useWorkflowsV2(workflowsQuery, { keepPreviousData: true });

  const isFirstLoading = isFilteredWorkflowsLoading && !filteredWorkflows;

  const isTableEmpty = filteredWorkflowsCount === 0;
  const isEmptyState =
    !isFilteredWorkflowsLoading && isTableEmpty && !workflowsQuery?.cel;

  const showFilterEmptyState = isTableEmpty && !!filterCel;
  const showSearchEmptyState =
    isTableEmpty && !!searchCel && !showFilterEmptyState;

  const setPaginationStateCallback = useCallback(
    (pageIndex: number, limit: number, offset: number) => {
      setPaginationState({ limit, offset });
    },
    [setPaginationState]
  );

  const facetsConfig: FacetsConfig = useMemo(() => {
    return {
      ["Last execution status"]: {
        renderOptionIcon: (facetOption) => {
          switch (facetOption.value) {
            case "success": {
              return <CheckCircleIcon className="w-5 h-5 text-green-500" />;
            }
            case "error":
            case "failed": {
              return <XCircleIcon className="w-5 h-5 text-red-500" />;
            }
            case "in_progress": {
              return <ArrowPathIcon className="w-5 h-5 text-orange-500" />;
            }
            default: {
              return (
                <ExclamationCircleIcon className="w-5 h-5 text-gray-500" />
              );
            }
          }
        },
        renderOptionLabel: (facetOption) => {
          switch (facetOption.value) {
            case "success": {
              return "Success";
            }
            case "error": {
              return "Error";
            }
            case "in_progress": {
              return "In progress";
            }
            case "":
            case null:
            case undefined: {
              return "Not run yet";
            }
            default: {
              return facetOption.value;
            }
          }
        },
      },
      ["Created by"]: {
        renderOptionIcon: (facetOption) => (
          <UserStatefulAvatar email={facetOption.display_name} size="xs" />
        ),
        renderOptionLabel: (facetOption) => {
          if (facetOption.display_name === "null") {
            return "Not assigned";
          }
          return <AssigneeLabel email={facetOption.display_name} />;
        },
      },
      ["Enabling status"]: {
        renderOptionLabel: (facetOption) =>
          ["true", "1"].includes(facetOption.display_name.toLocaleLowerCase())
            ? "Disabled"
            : "Enabled",
      },
    };
  }, []);

  function renderFilterEmptyState() {
    return (
      <>
        <div className="flex items-center h-full w-full">
          <div className="flex flex-col justify-center items-center w-full">
            <EmptyStateCard
              title="No workflows to display matching your filter"
              icon={FunnelIcon}
            >
              <Button
                color="orange"
                variant="secondary"
                onClick={() => setClearFiltersToken(uuidV4())}
              >
                Reset filter
              </Button>
            </EmptyStateCard>
          </div>
        </div>
      </>
    );
  }

  function renderSearchEmptyState() {
    return (
      <>
        <div className="flex items-center h-full w-full">
          <div className="flex flex-col justify-center items-center w-full">
            <EmptyStateCard
              title="No workflows to display matching your search"
              icon={MagnifyingGlassIcon}
            >
              <Button
                color="orange"
                variant="secondary"
                onClick={() => setSearchedValue(null)}
              >
                Clear search
              </Button>
            </EmptyStateCard>
          </div>
        </div>
      </>
    );
  }

  function renderData() {
    return (
      <div
        className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 w-full gap-4"
        data-testid="workflow-list"
      >
        {filteredWorkflows?.map((workflow) => (
          <WorkflowTile key={workflow.id} workflow={workflow} />
        ))}
      </div>
    );
  }

  if (error) {
    return <ErrorComponent error={error} reset={() => {}} />;
  }

  return (
    <>
      <main
        data-testid="workflows-exist-state"
        className="flex flex-col gap-12"
      >
        <div className="flex flex-col gap-6">
          <div className="flex justify-between items-end">
            <div>
              <PageTitle>Workflows</PageTitle>
              <PageSubtitle>
                Automate alert management with workflows
              </PageSubtitle>
            </div>
            <div className="flex gap-2">
              <Button
                color="orange"
                size="md"
                variant="secondary"
                onClick={() => {
                  setIsUploadWorkflowsModalOpen(true);
                }}
                icon={ArrowUpOnSquareStackIcon}
                id="uploadWorkflowButton"
              >
                Upload Workflows
              </Button>
              <Button
                color="orange"
                size="md"
                variant="primary"
                onClick={() => setIsCreateWorkflowModalOpen(true)}
                icon={PlusIcon}
              >
                Create Workflow
              </Button>
            </div>
          </div>
          {isEmptyState ? (
            <WorkflowsEmptyState />
          ) : (
            <div className="flex flex-col gap-6">
              <SearchInput
                className="flex-1"
                placeholder="Search workflows"
                value={searchedValue as string}
                onValueChange={setSearchedValue}
              />
              <div className="flex gap-6">
                <FacetsPanelServerSide
                  entityName={"workflows"}
                  facetsConfig={facetsConfig}
                  facetOptionsCel={searchCel}
                  usePropertyPathsSuggestions={true}
                  clearFiltersToken={clearFiltersToken}
                  initialFacetsData={initialFacetsData}
                  onCelChange={(cel) => setFilterCel(cel)}
                />

                <div className="flex flex-col flex-1 relative">
                  {isFirstLoading && (
                    <div className="flex items-center justify-center h-96 w-full">
                      <KeepLoader
                        includeMinHeight={false}
                        data-testid="keep-loader"
                      />
                    </div>
                  )}
                  {!isFirstLoading && (
                    <>
                      {showFilterEmptyState && renderFilterEmptyState()}
                      {showSearchEmptyState && renderSearchEmptyState()}
                      {!isTableEmpty && renderData()}
                    </>
                  )}
                  <div className={`mt-4 ${isFirstLoading ? "hidden" : ""}`}>
                    <Pagination
                      totalCount={filteredWorkflowsCount ?? 0}
                      isRefreshAllowed={false}
                      isRefreshing={false}
                      pageSizeOptions={[12, 24, 48]}
                      onRefresh={() => {}}
                      onStateChange={setPaginationStateCallback}
                    />
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </main>
      {isUploadWorkflowsModalOpen && (
        <UploadWorkflowsModal
          onClose={() => setIsUploadWorkflowsModalOpen(false)}
        />
      )}
      {isCreateWorkflowModalOpen && (
        <CreateWorkflowModal
          onClose={() => setIsCreateWorkflowModalOpen(false)}
        />
      )}
    </>
  );
}
