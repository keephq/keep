"use client";

import {
  ChangeEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { Subtitle, Button } from "@tremor/react";
import {
  ArrowUpOnSquareStackIcon,
  PlusCircleIcon,
} from "@heroicons/react/24/outline";
import { KeepLoader, PageTitle } from "@/shared/ui";
import WorkflowsEmptyState from "./noworkflows";
import WorkflowTile from "./workflow-tile";
import { ArrowRightIcon } from "@radix-ui/react-icons";
import { useRouter } from "next/navigation";
import Modal from "@/components/ui/Modal";
import { WorkflowTemplates } from "./mockworkflows";
import { useApi } from "@/shared/lib/hooks/useApi";
import { Input, ErrorComponent } from "@/shared/ui";
import { EmptyStateCard, Textarea } from "@/components/ui";
import { useWorkflowsV2, WorkflowsQuery } from "utils/hooks/useWorkflowsV2";
import { useWorkflowActions } from "@/entities/workflows/model/useWorkflowActions";
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
} from "@heroicons/react/24/outline";
import { useUser } from "@/entities/users/model/useUser";
import { Pagination, SearchInput } from "@/features/filter";
import { FacetsPanelServerSide } from "@/features/filter/facet-panel-server-side";
import { InitialFacetsData } from "@/features/filter/api";
import { v4 as uuidV4 } from "uuid";

const EXAMPLE_WORKFLOW_DEFINITIONS = {
  slack: `
    workflow:
      id: slack-demo
      description: Send a slack message when any alert is triggered or manually
      triggers:
        - type: alert
        - type: manual
      actions:
        - name: trigger-slack
          provider:
            type: slack
            config: " {{ providers.slack }} "
            with:
              message: "Workflow ran | reason: {{ event.trigger }}"
    `,
  sql: `
    workflow:
      id: bq-sql-query
      description: Run SQL on Bigquery and send the results to slack
      triggers:
        - type: manual
      steps:
        - name: get-sql-data
          provider:
            type: bigquery
            config: "{{ providers.bigquery-prod }}"
            with:
              query: "SELECT * FROM some_database LIMIT 1"
      actions:
        - name: trigger-slack
          provider:
            type: slack
            config: " {{ providers.slack-prod }} "
            with:
              message: "Results from the DB: ({{ steps.get-sql-data.results }})"
  `,
};

type ExampleWorkflowKey = keyof typeof EXAMPLE_WORKFLOW_DEFINITIONS;

const AssigneeLabel = ({ email }: { email: string }) => {
  const user = useUser(email);
  return user ? user.name : email;
};

export default function WorkflowsPage({
  initialFacetsData,
}: {
  initialFacetsData?: InitialFacetsData;
}) {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [workflowDefinition, setWorkflowDefinition] = useState("");
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [clearFiltersToken, setClearFiltersToken] = useState<string | null>(
    null
  );
  const [filterCel, setFilterCel] = useState<string | null>(null);
  const [searchedValue, setSearchedValue] = useState<string | null>(null);
  const [paginationState, setPaginationState] = useState<{
    offset: number;
    limit: number;
  } | null>(null);
  const [workflowsQuery, setWorkflowsQuery] = useState<WorkflowsQuery | null>(
    null
  );

  const searchCel = useMemo(() => {
    if (!searchedValue) {
      return;
    }

    return `name.contains("${searchedValue}") || description.contains("${searchedValue}")`;
  }, [searchedValue]);

  useEffect(() => {
    if (!paginationState) {
      return;
    }

    const celList = [searchCel, filterCel].filter((cel) => cel);
    const cel = celList.join(" && ");
    const query: WorkflowsQuery = {
      cel,
      limit: paginationState?.limit,
      offset: paginationState?.offset,
      sortBy: "createdAt",
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

  const { uploadWorkflowFiles } = useWorkflowActions();

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
      ["Status"]: {
        renderOptionIcon: (facetOption) => {
          switch (facetOption.value) {
            case "success": {
              return <CheckCircleIcon className="w-5 h-5 text-green-500" />;
            }
            case "failed": {
              return <XCircleIcon className="w-5 h-5 text-red-500" />;
            }
            default: {
              return (
                <ExclamationCircleIcon className="w-5 h-5 text-orange-500" />
              );
            }
          }
        },
        renderOptionLabel: (facetOption) => {
          if (!facetOption.value) {
            return "Not run yet";
          }

          return (
            facetOption.display_name.charAt(0).toUpperCase() +
            facetOption.display_name.slice(1)
          );
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
          facetOption.display_name.toLocaleLowerCase() === "true"
            ? "Disabled"
            : "Enabled",
      },
    };
  }, []);

  function renderFilterEmptyState() {
    return (
      <>
        <div className="flex items-center h-full w-full">
          <div className="flex flex-col justify-center items-center w-full p-4">
            <EmptyStateCard
              title="No workflows to display matching your filter"
              buttonText="Reset filter"
              renderIcon={() => (
                <FunnelIcon className="mx-auto h-7 w-7 text-tremor-content-subtle dark:text-dark-tremor-content-subtle" />
              )}
              onClick={() => setClearFiltersToken(uuidV4())}
            />
          </div>
        </div>
      </>
    );
  }

  function renderSearchEmptyState() {
    return (
      <>
        <div className="flex items-center h-full w-full">
          <div className="flex flex-col justify-center items-center w-full p-4">
            <EmptyStateCard
              title="No workflows to display matching your search"
              buttonText="Clear search"
              renderIcon={() => (
                <MagnifyingGlassIcon className="mx-auto h-7 w-7 text-tremor-content-subtle dark:text-dark-tremor-content-subtle" />
              )}
              onClick={() => setSearchedValue(null)}
            />
          </div>
        </div>
      </>
    );
  }

  function renderData() {
    return (
      <>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 w-full gap-4">
          {filteredWorkflows?.map((workflow) => (
            <WorkflowTile key={workflow.id} workflow={workflow} />
          ))}
        </div>
      </>
    );
  }

  if (error) {
    return <ErrorComponent error={error} reset={() => {}} />;
  }

  const onDrop = async (files: ChangeEvent<HTMLInputElement>) => {
    if (!files.target.files) {
      return;
    }

    const uploadedWorkflowsIds = await uploadWorkflowFiles(files.target.files);

    if (fileInputRef.current) {
      // Reset the file input to allow for multiple uploads
      fileInputRef.current.value = "";
    }

    setIsModalOpen(false);
    if (uploadedWorkflowsIds.length === 1) {
      // If there is only one file, redirect to the workflow detail page
      router.push(`/workflows/${uploadedWorkflowsIds[0]}`);
    }
  };

  function handleWorkflowDefinitionString(
    workflowDefinition: string,
    name: string = "New workflow"
  ) {
    const blob = new Blob([workflowDefinition], {
      type: "application/x-yaml",
    });
    const file = new File([blob], `${name}.yml`, {
      type: "application/x-yaml",
    });
    const event = {
      target: {
        files: [file],
      },
    };
    onDrop(event as any);
  }

  function handleStaticExampleSelect(exampleKey: ExampleWorkflowKey) {
    switch (exampleKey) {
      case "slack":
        handleWorkflowDefinitionString(EXAMPLE_WORKFLOW_DEFINITIONS.slack);
        break;
      case "sql":
        handleWorkflowDefinitionString(EXAMPLE_WORKFLOW_DEFINITIONS.sql);
        break;
      default:
        throw new Error(`Invalid example workflow key: ${exampleKey}`);
    }
    setIsModalOpen(false);
  }

  return (
    <>
      <main className="flex flex-col gap-8">
        <div className="flex flex-col gap-6">
          <div className="flex justify-between items-end">
            <div>
              <PageTitle>My Workflows</PageTitle>
              <PageSubtitle>
                Automate your alert management with workflows
              </PageSubtitle>
            </div>
            <SearchInput
              className="flex-1 mx-4"
              placeholder="Search workflows"
              value={searchedValue as string}
              onValueChange={setSearchedValue}
            />
            <div className="flex gap-2">
              <Button
                color="orange"
                size="md"
                variant="secondary"
                onClick={() => {
                  setIsModalOpen(true);
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
                onClick={() => router.push("/workflows/builder")}
                icon={PlusIcon}
              >
                Create Workflow
              </Button>
            </div>
          </div>
          {isEmptyState ? (
            <WorkflowsEmptyState isNewUI={true} />
          ) : (
            <div className="flex gap-4">
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
                    <KeepLoader includeMinHeight={false} />
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
                    totalCount={filteredWorkflowsCount}
                    isRefreshAllowed={false}
                    isRefreshing={false}
                    pageSizeOptions={[12, 24, 48]}
                    onRefresh={() => {}}
                    onStateChange={setPaginationStateCallback}
                  />
                </div>
              </div>
            </div>
          )}
        </div>
        <div className="flex flex-col gap-4">
          <WorkflowTemplates />
        </div>
      </main>
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title="Upload Workflow files"
      >
        <div className="bg-white rounded max-w-lg max-h-fit	 mx-auto z-20">
          <div className="space-y-2">
            <Input
              ref={fileInputRef}
              id="workflowFile"
              name="file"
              type="file"
              className="mt-2"
              accept=".yml, .yaml"
              multiple
              onChange={(e) => {
                onDrop(e);
                setIsModalOpen(false); // Add this line to close the modal
              }}
            />
            <p className="mt-2 text-xs text-gray-500 dark:text-gray-500">
              Only .yml and .yaml files are supported.
            </p>
          </div>
          <div className="mt-4">
            <h3>Or paste the YAML definition:</h3>
            <Textarea
              id="workflowDefinition"
              onChange={(e) => {
                setWorkflowDefinition(e.target.value);
              }}
              name="workflowDefinition"
              className="mt-2"
            />
            <Button
              className="mt-2"
              color="orange"
              size="md"
              variant="primary"
              onClick={() => handleWorkflowDefinitionString(workflowDefinition)}
            >
              Load
            </Button>
          </div>
          <div className="mt-4 text-sm">
            <h3>Or just try some from Keep examples:</h3>
            <Button
              className="mt-2"
              color="orange"
              size="md"
              variant="secondary"
              icon={ArrowRightIcon}
              onClick={() => handleStaticExampleSelect("slack")}
            >
              Send a Slack message for every alert or manually
            </Button>

            <Button
              className="mt-2"
              color="orange"
              size="md"
              variant="secondary"
              icon={ArrowRightIcon}
              onClick={() => handleStaticExampleSelect("sql")}
            >
              Run SQL query and send the results as a Slack message
            </Button>

            <p className="mt-2">
              More examples at{" "}
              <a
                href="https://github.com/keephq/keep/tree/main/examples/workflows"
                target="_blank"
              >
                Keep GitHub repo
              </a>
            </p>
          </div>

          <div className="mt-4">
            <Button
              className="mt-2"
              color="orange"
              variant="secondary"
              onClick={() => setIsModalOpen(false)}
            >
              Cancel
            </Button>
          </div>
        </div>
      </Modal>
    </>
  );
}
