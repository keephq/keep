import { render, screen } from "@testing-library/react";
import { ManualRunWorkflowModal } from "../manual-run-workflow-modal";
import { useWorkflowsV2 } from "@/entities/workflows/model/useWorkflowsV2";
import { Workflow } from "@/shared/api/workflows";

jest.mock("@/entities/workflows/model/useWorkflowsV2", () => ({
  DEFAULT_WORKFLOWS_QUERY: {},
  useWorkflowsV2: jest.fn(),
}));
jest.mock("@/components/ui/Modal", () => ({
  __esModule: true,
  default: ({ children }: any) => <div>{children}</div>,
}));
jest.mock("@/shared/ui", () => ({
  Select: ({ options }: { options: Workflow[] }) => (
    <select aria-label="Workflows">
      {options.map((w) => (
        <option key={w.id}>{w.name}</option>
      ))}
    </select>
  ),
  showErrorToast: jest.fn(),
  showSuccessToast: jest.fn(),
}));

const workflows = [
  { id: "z", name: "Zulu", canRun: true },
  { id: "hidden", name: "Hidden", canRun: true, manual_visible: false },
  { id: "a", name: "alpha", canRun: true, manual_visible: true },
  { id: "denied", name: "Denied", canRun: false },
] as Workflow[];

it("shows permitted, visible workflows alphabetically without changing cached results", () => {
  (useWorkflowsV2 as jest.Mock).mockReturnValue({ workflows });
  render(<ManualRunWorkflowModal isOpen onClose={() => {}} />);
  expect(screen.getAllByRole("option").map((o) => o.textContent)).toEqual([
    "alpha",
    "Zulu",
  ]);
  expect(workflows.map((w) => w.id)).toEqual(["z", "hidden", "a", "denied"]);
  expect(useWorkflowsV2).toHaveBeenCalledWith(
    expect.objectContaining({ sortBy: "name", sortDir: "asc" })
  );
  expect(screen.getByText(/lack permissions/)).toBeInTheDocument();
});

it("does not report hidden workflows as a permissions problem", () => {
  (useWorkflowsV2 as jest.Mock).mockReturnValue({
    workflows: workflows.filter((w) => w.canRun),
  });
  render(<ManualRunWorkflowModal isOpen onClose={() => {}} />);
  expect(screen.queryByText(/lack permissions/)).not.toBeInTheDocument();
});

it("shows an empty state when all workflows are hidden", () => {
  (useWorkflowsV2 as jest.Mock).mockReturnValue({ workflows: [workflows[1]] });
  render(<ManualRunWorkflowModal isOpen onClose={() => {}} />);
  expect(screen.getByText("No workflows found")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Run" })).toBeDisabled();
});
