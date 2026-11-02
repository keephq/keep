import { useState } from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { AlertDto } from "@/entities/alerts/model";
import { ManualRunWorkflowModal } from "../manual-run-workflow-modal";

jest.mock("@/components/ui/Modal", () => ({
  __esModule: true,
  default: ({ isOpen, children }: any) =>
    isOpen ? <div>{children}</div> : null,
}));
jest.mock("@/shared/lib/hooks/useApi", () => ({
  useApi: jest.fn(() => ({ post: jest.fn() })),
}));
jest.mock("@/entities/workflows/model/useWorkflowsV2", () => ({
  DEFAULT_WORKFLOWS_QUERY: {},
  useWorkflowsV2: jest.fn(() => ({
    workflows: [
      {
        id: "wf-1",
        name: "Sample workflow",
        description: "A sample manual workflow",
        created_by: "someone",
        canRun: true,
        triggers: [],
      },
    ],
  })),
}));
jest.mock("@/entities/workflows/ui/WorkflowTriggerBadge", () => ({
  WorkflowTriggerBadge: () => null,
}));

describe("ManualRunWorkflowModal workflow select", () => {
  it("keeps the dropdown open when the modal re-renders", () => {
    const alert = { name: "alert", fingerprint: "fp" } as AlertDto;

    function Harness() {
      // stands in for the alerts page re-rendering on every poll-alerts event
      const [, setTick] = useState(0);
      return (
        <div>
          <button onClick={() => setTick((t) => t + 1)}>rerender</button>
          <ManualRunWorkflowModal alert={alert} onClose={() => {}} />
        </div>
      );
    }

    render(<Harness />);
    fireEvent.mouseDown(
      screen.getByTestId("manual-run-workflow-select-control")
    );
    expect(screen.getByText("Sample workflow")).toBeTruthy();

    fireEvent.click(screen.getByText("rerender"));
    fireEvent.click(screen.getByText("rerender"));

    expect(screen.getByText("Sample workflow")).toBeTruthy();
  });
});
