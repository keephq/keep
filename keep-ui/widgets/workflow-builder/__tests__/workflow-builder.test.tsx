import { render, screen } from "@testing-library/react";
import { WorkflowBuilder } from "../workflow-builder";
import { WorkflowState } from "@/entities/workflows";
import { InternalConfig } from "@/types/internal-config";
import { getYamlWorkflowDefinitionSchema } from "@/entities/workflows/model/yaml.schema";

// Mock next-auth
jest.mock("next-auth/react", () => ({
  SessionProvider: ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  ),
  useSession: () => ({
    data: {
      user: {
        id: "test-user-id",
        name: "Test User",
        email: "test@example.com",
        image: null,
        accessToken: "test-token",
      },
      expires: "2024-12-31",
    },
    status: "authenticated",
  }),
}));

// Mock all ES module imports
jest.mock("@/features/workflows/builder", () => ({
  __esModule: true,
  ReactFlowBuilder: function MockReactFlowBuilder() {
    const { useWorkflowStore } = require("@/entities/workflows");
    const { nodes } = useWorkflowStore();
    return (
      <div data-testid="react-flow-builder">
        {nodes.map((node: { id: string; data: { name: string } }) => (
          <div key={node.id} data-testid={`workflow-node-${node.id}`}>
            {node.data.name}
          </div>
        ))}
      </div>
    );
  },
}));

jest.mock("@xyflow/react", () => ({
  ReactFlowProvider: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="react-flow-provider">{children}</div>
  ),
}));

jest.mock("@/features/workflows/ai-assistant", () => ({
  WorkflowBuilderChatSafe: () => <div>WorkflowBuilderChat</div>,
}));

jest.mock("@/shared/ui/WorkflowYAMLEditor", () => ({
  __esModule: true,
  WorkflowYAMLEditor: () => <div>WorkflowYAMLEditor</div>,
}));

jest.mock("next/navigation", () => ({
  useRouter: () => ({
    push: jest.fn(),
  }),
  useSearchParams: () => null,
}));

// Mock useWorkflowActions
jest.mock("@/entities/workflows/model/useWorkflowActions", () => ({
  useWorkflowActions: () => ({
    createWorkflow: jest.fn(),
    updateWorkflow: jest.fn(),
  }),
}));

// Mock store
const mockStore: WorkflowState = {
  definition: {
    value: {
      sequence: [
        {
          id: "step1",
          name: "First Step",
          type: "step-test",
          componentType: "task",
          properties: {
            stepParams: [],
            with: {},
            if: "",
            vars: {},
          },
        },
        {
          id: "step2",
          name: "Second Step",
          type: "step-test",
          componentType: "task",
          properties: {
            stepParams: [],
          },
        },
      ],
      properties: {
        id: "test-workflow",
        name: "Test Workflow",
        description: "Test workflow description",
        disabled: false,
        isLocked: false,
        consts: {},
        manual: "true",
        interval: 10,
        alert: {},
        incident: { events: ["created", "updated", "deleted"] },
      },
    },
    isValid: true,
  },
  yamlSchema: getYamlWorkflowDefinitionSchema([], { partial: true }),
  isInitialized: true,
  isEditorSyncedWithNodes: true,
  canDeploy: true,
  isSaving: false,
  v2Properties: {},
  isLoading: false,
  saveRequestCount: 0,
  testRunRequestCount: 0,
  lastChangedAt: 0,
  lastDeployedAt: 0,
  editorOpen: false,
  toolboxConfiguration: null,
  providers: null,
  installedProviders: null,
  workflowId: "test-workflow",
  nodes: [],
  edges: [],
  selectedNode: null,
  selectedEdge: null,
  isLayouted: false,
  changes: 0,
  isDeployed: false,
  validationErrors: {},
  triggerSave: jest.fn(),
  triggerTestRun: jest.fn(),
  updateV2Properties: jest.fn(),
  setDefinition: jest.fn(),
  setIsLoading: jest.fn(),
  setIsSaving: jest.fn(),
  setLastDeployedAt: jest.fn(),
  reset: jest.fn(),
  initializeWorkflow: jest.fn(),
  setProviders: jest.fn(),
  setInstalledProviders: jest.fn(),
  setCanDeploy: jest.fn(),
  setEditorSynced: jest.fn(),
  setSelectedEdge: jest.fn(),
  setIsLayouted: jest.fn(),
  addNodeBetween: jest.fn(),
  addNodeBetweenSafe: jest.fn(),
  updateDefinition: jest.fn(),
  onConnect: jest.fn(),
  onDragOver: jest.fn(),
  onDrop: jest.fn(),
  setNodes: jest.fn(),
  setEdges: jest.fn(),
  getNodeById: jest.fn(),
  getEdgeById: jest.fn(),
  deleteNodes: jest.fn(),
  getNextEdge: jest.fn(),
  setEditorOpen: jest.fn(),
  updateSelectedNodeData: jest.fn(),
  setSelectedNode: jest.fn(),
  onNodesChange: jest.fn(),
  onEdgesChange: jest.fn(),
  onLayout: jest.fn(),
  updateFromYamlString: jest.fn(),
  setSecrets: jest.fn(),
  validateDefinition: jest.fn(),
  secrets: {},
};

const mockedUseWorkflowStore = jest.fn(() => mockStore);

jest.mock("@/entities/workflows", () => ({
  useWorkflowStore: () => mockedUseWorkflowStore(),
}));

const mockConfig: InternalConfig = {
  API_URL: "http://localhost:8000",
  API_URL_CLIENT: "http://localhost:8000",
  AUTH_TYPE: "test",
  PUSHER_DISABLED: false,
  PUSHER_HOST: "localhost",
  PUSHER_PORT: 6001,
  PUSHER_APP_KEY: "test",
  PUSHER_CLUSTER: "test",
  POSTHOG_KEY: "test",
  POSTHOG_HOST: "localhost",
  POSTHOG_DISABLED: "true",
  READ_ONLY: false,
  OPEN_AI_API_KEY_SET: false,
  NOISY_ALERTS_ENABLED: false,
  FRIGADE_DISABLED: "false",
  KEEP_DOCS_URL: "https://docs.keephq.dev",
  KEEP_CONTACT_US_URL: "https://docs.keephq.dev/slack",
  SENTRY_DISABLED: "true",
};

jest.mock("@/utils/hooks/useConfig", () => ({
  useConfig: () => ({
    data: mockConfig,
  }),
}));

const mockProvider = {
  id: "mock-provider",
  type: "mock",
  config: {},
  installed: true,
  linked: true,
  last_alert_received: "",
  details: {
    authentication: {},
  },
  display_name: "Mock Provider",
  can_query: true,
  can_notify: true,
  validatedScopes: {},
  tags: [],
  pulling_available: true,
  pulling_enabled: true,
  health: true,
  categories: [],
  coming_soon: false,
};

describe("WorkflowBuilder", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("should render workflow with nodes", () => {
    const workflowRaw = JSON.stringify({
      sequence: [
        {
          id: "step1",
          name: "First Step",
          type: "step-test",
          componentType: "task",
        },
        {
          id: "step2",
          name: "Second Step",
          type: "step-test",
          componentType: "task",
        },
      ],
      properties: {
        name: "Test Workflow",
        description: "Test workflow description",
      },
    });

    // Mock the workflow store to include our test nodes
    const mockNodes = [
      {
        id: "step1",
        data: { name: "First Step", type: "step-test", componentType: "task" },
      },
      {
        id: "step2",
        data: { name: "Second Step", type: "step-test", componentType: "task" },
      },
    ];

    const mockedStore = {
      ...mockStore,
      nodes: mockNodes,
      isLayouted: true,
    };

    jest
      .spyOn(require("@/entities/workflows"), "useWorkflowStore")
      .mockImplementation(() => mockedStore);

    render(
      <WorkflowBuilder
        workflowRaw={workflowRaw}
        workflowId="test-workflow"
        providers={[mockProvider]}
        installedProviders={[mockProvider]}
        loadedYamlFileContents={null}
      />
    );

    // Verify ReactFlowBuilder is rendered
    expect(screen.getByTestId("react-flow-builder")).toBeInTheDocument();

    // Verify step names are present
    expect(screen.getByText("First Step")).toBeInTheDocument();
    expect(screen.getByText("Second Step")).toBeInTheDocument();
  });

  it("should show loading state", () => {
    // Mock loading state
    const mockedStore = {
      ...mockStore,
      isLoading: true,
    };

    jest
      .spyOn(require("@/entities/workflows"), "useWorkflowStore")
      .mockImplementation(() => mockedStore);

    render(
      <WorkflowBuilder
        workflowRaw=""
        workflowId="test-workflow"
        providers={[mockProvider]}
        installedProviders={[mockProvider]}
        loadedYamlFileContents={null}
      />
    );

    expect(screen.getByText("Loading workflow...")).toBeInTheDocument();
  });
});
