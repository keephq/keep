import { act, render, renderHook } from "@testing-library/react";
import "@testing-library/jest-dom";
import ReactFlowBuilder from "../ReactFlowBuilder";
import { ReactFlowProvider } from "@xyflow/react";
import { useWorkflowStore } from "@/entities/workflows";

// Mock the hooks and components
jest.mock("../ReactFlowEditor", () => ({
  __esModule: true,
  default: () => <div data-testid="flow-editor">Flow Editor</div>,
}));

// Mock minimal props
const mockProps = {
  workflowId: null,
  providers: [],
  installedProviders: [],
};

describe("ReactFlowBuilder", () => {
  beforeAll(() => {
    // Mock ResizeObserver
    window.ResizeObserver = jest.fn().mockImplementation(() => ({
      observe: jest.fn(),
      unobserve: jest.fn(),
      disconnect: jest.fn(),
    }));
  });

  it("renders successfully", () => {
    const { result } = renderHook(() => useWorkflowStore());

    act(() => {
      result.current.setDefinition({
        value: {
          sequence: [],
          properties: {},
        },
        isValid: true,
      });
    });

    const { getByTestId } = render(
      <ReactFlowProvider>
        <ReactFlowBuilder {...mockProps} />
      </ReactFlowProvider>
    );

    // Check if main components are rendered using test IDs
    expect(getByTestId("flow-editor")).toBeInTheDocument();
  });
});
