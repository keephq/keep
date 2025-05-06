import Modal from "@/components/ui/Modal";
import "react-loading-skeleton/dist/skeleton.css";
import { useQueryWorkflowTemplate } from "./use-query-workflow-template";
import { useCallback, useMemo, useState } from "react";
import { SearchInput } from "@/features/filter";
import { Pagination, PaginationState } from "@/features/filter/pagination";
import { WorkflowTemplateCard } from "./workflow-template-card";
import { useRouter } from "next/navigation";
import { ErrorComponent } from "@/shared/ui";
import { MagnifyingGlassIcon } from "@heroicons/react/24/outline";
import { Button } from "@tremor/react";

interface CreateWorkflowModalProps {
  onClose: () => void;
}

const CreateWorkflowModal: React.FC<CreateWorkflowModalProps> = ({
  onClose,
}) => {
  const router = useRouter();

  const [searchValue, setSearchValue] = useState("");
  const [paginationState, setPaginationState] = useState<PaginationState>({
    offset: 0,
    limit: 12,
  });

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

  const setPaginationStateCallback = useCallback(
    (pageIndex: number, limit: number, offset: number) => {
      setPaginationState({ limit, offset });
    },
    [setPaginationState]
  );

  function renderBody() {
    if (mockError) {
      return <ErrorComponent error={mockError} reset={() => refresh()} />;
    }

    if (cartsToRender.length === 0) {
      return (
        <div className="flex items-center h-[640px]">
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
        <div className="min-h-[640px]">
          <div className="flex-1  grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 w-full gap-4">
            {cartsToRender.map((template, index: number) => (
              <WorkflowTemplateCard key={index} template={template} />
            ))}
          </div>
        </div>
        <div className={mockLoading ? "hidden" : ""}>
          <Pagination
            totalCount={totalCount ?? 0}
            isRefreshAllowed={false}
            isRefreshing={false}
            pageSizeOptions={[12]}
            onRefresh={() => {}}
            onStateChange={setPaginationStateCallback}
          />
        </div>
      </>
    );
  }

  return (
    <Modal
      isOpen={true}
      onClose={onClose}
      className="min-w-[80vw] min-h-[90vh]"
      title="Create workflow"
    >
      <div className="flex flex-col gap-3 h-full w-full">
        <div className="text-lg">
          <p>
            Choose a workflow template to start building the automation for your
            alerts and incidents.
          </p>
          <p className="pt-2 pb-1">
            Or skip this, and{" "}
            <Button
              className="ml-2"
              color="orange"
              size="xs"
              variant="primary"
              onClick={() => router.push("/workflows/builder")}
            >
              Start from scratch
            </Button>
          </p>
        </div>

        <SearchInput
          placeholder="Search workflows"
          value={searchValue as string}
          onValueChange={setSearchValue}
        />
        {renderBody()}
      </div>
    </Modal>
  );
};

export default CreateWorkflowModal;
