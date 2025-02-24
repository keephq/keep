import { render, screen } from "@testing-library/react";
import { WorkflowBuilderWidgetSafe } from "../workflow-builder-widget-safe";
import { useConfig } from "@/utils/hooks/useConfig";
import { WorkflowBuilderWidget } from "../workflow-builder-widget";

// Mock the actual WorkflowBuilderWidget component
jest.mock("../workflow-builder-widget", () => ({
  WorkflowBuilderWidget: jest.fn(({ workflowRaw, workflowId }) => (
    <div data-testid="workflow-builder">
      <span>workflowRaw: {workflowRaw}</span>
      <span>workflowId: {workflowId}</span>
    </div>
  )),
}));

// Mock CopilotKit
jest.mock("@copilotkit/react-core", () => ({
  CopilotKit: ({ children, runtimeUrl: _, ...props }: any) => (
    <div data-testid="copilot-wrapper" {...props}>
      {children}
    </div>
  ),
}));

// Mock useConfig hook
jest.mock("@/utils/hooks/useConfig", () => ({
  useConfig: jest.fn(),
}));

describe("WorkflowBuilderWidgetSafe", () => {
  const mockWorkflowRaw = JSON.stringify({ test: "workflow" });
  const mockWorkflowId = "test-workflow-id";

  beforeEach(() => {
    jest.clearAllMocks();
    (WorkflowBuilderWidget as jest.Mock).mockClear();
  });

  it("should render WorkflowBuilderWidget with props when OpenAI key is not set", () => {
    // Mock useConfig to return OpenAI key not set
    (useConfig as jest.Mock).mockReturnValue({
      data: { OPEN_AI_API_KEY_SET: false },
    });

    render(
      <WorkflowBuilderWidgetSafe
        workflowRaw={mockWorkflowRaw}
        workflowId={mockWorkflowId}
      />
    );

    // Verify WorkflowBuilderWidget was called with correct props
    expect(WorkflowBuilderWidget).toHaveBeenCalledWith(
      expect.objectContaining({
        workflowRaw: mockWorkflowRaw,
        workflowId: mockWorkflowId,
      }),
      expect.anything()
    );

    // Verify the rendered content
    expect(screen.getByTestId("workflow-builder")).toBeInTheDocument();
    expect(
      screen.getByText(`workflowRaw: ${mockWorkflowRaw}`)
    ).toBeInTheDocument();
    expect(
      screen.getByText(`workflowId: ${mockWorkflowId}`)
    ).toBeInTheDocument();
  });

  it("should wrap WorkflowBuilderWidget with CopilotKit when OpenAI key is set", () => {
    // Mock useConfig to return OpenAI key set
    (useConfig as jest.Mock).mockReturnValue({
      data: { OPEN_AI_API_KEY_SET: true },
    });

    render(
      <WorkflowBuilderWidgetSafe
        workflowRaw={mockWorkflowRaw}
        workflowId={mockWorkflowId}
      />
    );

    // Verify CopilotKit wrapper is present
    expect(screen.getByTestId("copilot-wrapper")).toBeInTheDocument();

    // Verify WorkflowBuilderWidget was called with correct props
    expect(WorkflowBuilderWidget).toHaveBeenCalledWith(
      expect.objectContaining({
        workflowRaw: mockWorkflowRaw,
        workflowId: mockWorkflowId,
      }),
      expect.anything()
    );

    // Verify the rendered content is inside CopilotKit
    const copilotWrapper = screen.getByTestId("copilot-wrapper");
    expect(copilotWrapper).toContainElement(
      screen.getByTestId("workflow-builder")
    );
  });
});
