import { render } from "@testing-library/react";
import "@testing-library/jest-dom";
import ReactFlowBuilder from "../ReactFlowBuilder";
import { ReactFlowProvider } from "@xyflow/react";

// Mock the hooks and components
jest.mock("../ToolBox", () => ({
  __esModule: true,
  default: () => <div data-testid="toolbox">Toolbox</div>,
}));

jest.mock("../ReactFlowEditor", () => ({
  __esModule: true,
  default: () => <div data-testid="flow-editor">Flow Editor</div>,
}));

// Mock minimal props
const mockProps = {
  providers: [],
  installedProviders: [],
  toolboxConfiguration: {},
  definition: {
    sequence: [],
    properties: {},
  },
  validatorConfiguration: {
    step: jest.fn(() => true),
    root: jest.fn(() => true),
  },
  onDefinitionChange: jest.fn(),
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
    jest.mock("@/utils/hooks/useWorkflowInitialization", () => ({
      __esModule: true,
      default: () => ({
        nodes: [],
        edges: [],
        isLoading: false,
        onEdgesChange: jest.fn(),
        onNodesChange: jest.fn(),
        onConnect: jest.fn(),
        onDragOver: jest.fn(),
        onDrop: jest.fn(),
      }),
    }));

    const { getByTestId } = render(
      <ReactFlowProvider>
        <ReactFlowBuilder {...mockProps} />
      </ReactFlowProvider>
    );

    // Check if main components are rendered using test IDs
    expect(getByTestId("toolbox")).toBeInTheDocument();
    expect(getByTestId("flow-editor")).toBeInTheDocument();
  });
});
