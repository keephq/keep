import { act, fireEvent, getByText, render } from "@testing-library/react";
import { ExistingWorkflowsState } from "../existing-workflows-state";
import { useWorkflowsV2 } from "@/entities/workflows/model/useWorkflowsV2";
import { useWorkflowActions } from "@/entities/workflows/model/useWorkflowActions";
import { mockWorkflow } from "@/entities/workflows/model/__mocks__/mock-workflow";

jest.mock("@/entities/workflows/model/useWorkflowsV2", () => ({
  useWorkflowsV2: jest.fn(),
  DEFAULT_WORKFLOWS_PAGINATION: {
    offset: 0,
    limit: 12,
  },
  DEFAULT_WORKFLOWS_QUERY: {
    cel: "",
  },
}));

jest.mock("@/entities/workflows/model/useWorkflowActions", () => ({
  useWorkflowActions: jest.fn().mockReturnValue({
    createWorkflow: jest.fn(),
    updateWorkflow: jest.fn(),
    deleteWorkflow: jest.fn(),
    uploadWorkflowFiles: jest.fn(),
  }),
}));

jest.mock("@/features/workflows/manual-run-workflow", () => ({
  useWorkflowRun: jest.fn(),
  useWorkflowModals: jest.fn().mockReturnValue({
    openInputsModal: jest.fn(),
    openAlertDependenciesModal: jest.fn(),
    openIncidentDependenciesModal: jest.fn(),
    openUnsavedChangesModal: jest.fn(),
    closeAllModals: jest.fn(),
  }),
}));

jest.mock("@/features/filter/facet-panel-server-side", () => ({
  FacetsPanelServerSide: () => <div data-testid="facets-panel" />,
}));

describe("WorkflowsPage", () => {
  afterEach(() => {
    jest.clearAllMocks();
  });

  it("should render", async () => {
    (useWorkflowsV2 as jest.Mock).mockReturnValue({
      workflows: [mockWorkflow],
      totalCount: 1,
      isLoading: false,
      error: null,
    });

    const { getByTestId } = render(<ExistingWorkflowsState />);

    expect(getByTestId("workflow-list")).toBeInTheDocument();
  });

  it("should call deleteWorkflow when delete button is clicked", async () => {
    (useWorkflowsV2 as jest.Mock).mockReturnValue({
      workflows: [mockWorkflow, { ...mockWorkflow, id: "2" }],
      totalCount: 2,
      isLoading: false,
      error: null,
    });

    const { getByTestId } = render(<ExistingWorkflowsState />);

    await act(async () => {
      const workflowList = getByTestId("workflow-list");
      const threeDotsMenu = workflowList.querySelectorAll(
        "[data-testid='workflow-menu']"
      );
      const dropdownMenuButton = threeDotsMenu[1].querySelector(
        "[data-testid='dropdown-menu-button']"
      );

      if (!dropdownMenuButton) {
        throw new Error("Dropdown menu button not found");
      }
      await fireEvent.click(dropdownMenuButton);
      const deleteButton = getByTestId("wf-menu-delete-button");
      await fireEvent.click(deleteButton);
    });

    const deleteFunction = (useWorkflowActions as jest.Mock).mock.results[0]
      .value.deleteWorkflow;

    expect(deleteFunction).toHaveBeenCalledWith("2");
  });
});
