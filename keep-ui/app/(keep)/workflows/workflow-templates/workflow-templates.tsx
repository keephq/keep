import "react-loading-skeleton/dist/skeleton.css";
import { useCallback, useEffect, useMemo, useState } from "react";
import { SearchInput } from "@/features/filter";
import { Pagination, PaginationState } from "@/features/filter/pagination";
import { WorkflowTemplateCard } from "./workflow-template-card";
import { ErrorComponent } from "@/shared/ui";
import { MagnifyingGlassIcon } from "@heroicons/react/24/outline";
import { Button } from "@tremor/react";
import { useQueryWorkflowTemplate } from "@/entities/workflows/lib/use-query-workflow-template";

interface WorkflowTemplatesProps {}

export const WorkflowTemplates: React.FC<WorkflowTemplatesProps> = () => {
  const [searchValue, setSearchValue] = useState("");
  const [paginationState, setPaginationState] = useState<PaginationState>({
    offset: 0,
    limit: 12,
  });
  useEffect(
    () => setPaginationState({ offset: 0, limit: 12 }),
    [searchValue, setPaginationState]
  );

  const query = useMemo(() => {
    const cel = searchValue
      ? `name.contains("${searchValue}") || description.contains("${searchValue}")`
      : "";
    return {
      cel,
      limit: paginationState.limit,
      offset: paginationState.offset,
    };
  }, [searchValue, paginationState]);

  const {
    data: mockWorkflows,
    totalCount,
    error: mockError,
    isLoading: mockLoading,
    mutate: refresh,
  } = useQueryWorkflowTemplate(query, {
    revalidateOnFocus: false,
  });

  const cartsToRender = useMemo(() => {
    if (mockLoading || !mockWorkflows) {
      return new Array(paginationState.limit).fill(undefined);
    }

    return mockWorkflows;
  }, [mockWorkflows, mockLoading, paginationState]);

  function renderBody() {
    if (mockError) {
      return <ErrorComponent error={mockError} reset={() => refresh()} />;
    }

    if (cartsToRender.length === 0) {
      return (
        <div className="flex-1 min-h-0 flex items-center">
          <div className="flex flex-col justify-center items-center w-full">
            <div className="flex flex-col items-center justify-center max-w-md">
              <MagnifyingGlassIcon
                className="mx-auto size-8 text-tremor-content-strong/80"
                aria-hidden={true}
              />
              <p className="mt-2 text-xl font-semibold text-tremor-content-strong dark:text-dark-tremor-content-strong">
                No workflows to display matching your search
              </p>
            </div>
            <Button
              className="mt-4"
              color="orange"
              variant="secondary"
              onClick={() => setSearchValue("")}
            >
              Clear search
            </Button>
          </div>
        </div>
      );
    }

    return (
      <>
        <div className="flex-1 min-h-0 overflow-y-auto p-[1px]">
          <div className="flex-1  grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 w-full gap-4">
            {cartsToRender.map((template, index: number) => (
              <WorkflowTemplateCard key={index} template={template} />
            ))}
          </div>
        </div>
        <div className={mockLoading ? "hidden" : ""}>
          <Pagination
            key={searchValue}
            totalCount={totalCount ?? 0}
            isRefreshAllowed={false}
            isRefreshing={false}
            pageSizeOptions={[12]}
            onRefresh={() => {}}
            state={paginationState}
            onStateChange={setPaginationState}
          />
        </div>
      </>
    );
  }

  return (
    <div className="flex-1 min-h-0 flex flex-col gap-3">
      <SearchInput
        placeholder="Search workflows"
        value={searchValue as string}
        onValueChange={setSearchValue}
      />
      {renderBody()}
    </div>
  );
};
