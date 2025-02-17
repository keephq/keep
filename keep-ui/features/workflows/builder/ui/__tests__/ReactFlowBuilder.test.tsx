import { act, render, renderHook } from "@testing-library/react";
import "@testing-library/jest-dom";
import ReactFlowBuilder from "../ReactFlowBuilder";
import { ReactFlowProvider } from "@xyflow/react";
import { useWorkflowStore } from "@/entities/workflows";

// Mock the hooks and components
jest.mock("../Editor/ReactFlowEditor", () => ({
  __esModule: true,
  default: () => <div data-testid="flow-editor">Flow Editor</div>,
}));

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
        <ReactFlowBuilder />
      </ReactFlowProvider>
    );

    // Check if main components are rendered using test IDs
    expect(getByTestId("flow-editor")).toBeInTheDocument();
  });
});
