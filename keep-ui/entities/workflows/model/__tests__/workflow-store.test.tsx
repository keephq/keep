import { act, renderHook } from "@testing-library/react";
import {
  useWorkflowStore,
  FlowNode,
  V2StepTrigger,
} from "@/entities/workflows";
import { v4 as uuidv4 } from "uuid";
import { Connection } from "@xyflow/react";
import { Provider } from "@/shared/api/providers";

// Mock uuid to return predictable values
jest.mock("uuid", () => ({
  v4: jest.fn(),
}));

// First declare the mock function
const showErrorToastMock = jest.fn();

// Mock the entire module path
jest.mock("../../../../shared/ui/utils/showErrorToast", () => ({
  showErrorToast: () => showErrorToastMock(),
}));

const mockProvider: Provider = {
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

const notInstalledProvider: Provider = {
  ...mockProvider,
  type: "notinstalled",
  installed: false,
};

const mockProvidersConfiguration = {
  providers: [mockProvider, notInstalledProvider],
  installedProviders: [mockProvider],
};

describe("useWorkflowStore", () => {
  beforeEach(() => {
    // Reset all mocks before each test
    jest.clearAllMocks();

    // Reset the store before each test
    const { result } = renderHook(() => useWorkflowStore());
    act(() => {
      result.current.reset();
    });
  });

  describe("addNodeBetween", () => {
    it("should add a node between trigger_start and trigger_end for trigger components", () => {
      const { result } = renderHook(() => useWorkflowStore());
      const mockUuid = "test-uuid";
      (uuidv4 as jest.Mock).mockReturnValue(mockUuid);

      // Setup initial state
      act(() => {
        result.current.setNodes([
          {
            id: "trigger_start",
            type: "trigger",
            position: { x: 0, y: 0 },
            data: { type: "trigger" },
            isNested: false,
          } as FlowNode,
          {
            id: "trigger_end",
            type: "trigger",
            position: { x: 100, y: 100 },
            data: { type: "trigger" },
            isNested: false,
          } as FlowNode,
        ]);
        result.current.setEdges([
          { id: "edge-1", source: "trigger_start", target: "trigger_end" },
        ]);
      });

      // Add a trigger node
      act(() => {
        result.current.addNodeBetweenSafe(
          "edge-1",
          {
            id: "interval",
            componentType: "trigger",
            type: "interval",
            properties: {
              interval: "5m",
            },
            name: "Interval Trigger",
          } as V2StepTrigger,
          "edge"
        );
      });

      // Verify the node was added correctly
      expect(result.current.nodes).toHaveLength(3);
      expect(result.current.edges).toHaveLength(2);
      expect(result.current.v2Properties).toHaveProperty("interval", "5m");
    });

    it("should not add trigger component if one already exists", () => {
      const { result } = renderHook(() => useWorkflowStore());

      // Setup initial state with existing trigger
      act(() => {
        result.current.setDefinition({
          value: {
            sequence: [],
            properties: {
              id: "test",
              disabled: false,
              name: "test",
              description: "test",
              interval: "5m",
              isLocked: false,
              consts: {},
            },
          },
          isValid: true,
        });
        result.current.initializeWorkflow(null, mockProvidersConfiguration);
      });

      expect(result.current.nodes.map((node) => node.id)).toEqual([
        "start",
        "trigger_start",
        "interval",
        "trigger_end",
        "end",
      ]);

      // Try to add another trigger
      act(() => {
        const edges = result.current.edges;
        result.current.addNodeBetweenSafe(
          edges[1].id,
          {
            id: "interval",
            componentType: "trigger",
            type: "interval",
            properties: {
              interval: "6m",
            },
            name: "Interval Trigger",
          } as V2StepTrigger,
          "edge"
        );
      });

      // Verify no new node was added
      expect(showErrorToastMock).toHaveBeenCalled();
      expect(result.current.nodes).toHaveLength(5);
      expect(result.current.v2Properties).toHaveProperty("interval", "5m");
    });
  });

  describe("deleteNodes", () => {
    it("should delete a node and reconnect its edges", () => {
      const { result } = renderHook(() => useWorkflowStore());

      // Setup initial state
      act(() => {
        result.current.setNodes([
          {
            id: "node1",
            data: { type: "step" },
            position: { x: 0, y: 0 },
            isNested: false,
          } as FlowNode,
          {
            id: "node2",
            data: { type: "step" },
            position: { x: 50, y: 50 },
            isNested: false,
          } as FlowNode,
          {
            id: "node3",
            data: { type: "step" },
            position: { x: 100, y: 100 },
            isNested: false,
          } as FlowNode,
        ]);
        result.current.setEdges([
          { id: "edge1", source: "node1", target: "node2" },
          { id: "edge2", source: "node2", target: "node3" },
        ]);
      });

      // Delete middle node
      act(() => {
        result.current.deleteNodes("node2");
      });

      // Verify edges were reconnected
      expect(result.current.nodes).toHaveLength(2);
      expect(result.current.edges).toHaveLength(1);
      expect(result.current.edges[0]).toMatchObject({
        source: "node1",
        target: "node3",
      });
    });

    it("should clean up v2Properties when deleting trigger nodes", () => {
      const { result } = renderHook(() => useWorkflowStore());

      // Setup initial state with trigger node
      act(() => {
        result.current.setDefinition({
          value: {
            sequence: [],
            properties: {
              id: "test",
              disabled: false,
              name: "test",
              description: "test",
              interval: "5m",
              isLocked: false,
              consts: {},
            },
          },
          isValid: true,
        });
        result.current.initializeWorkflow(null, mockProvidersConfiguration);
      });

      // Delete interval trigger
      act(() => {
        result.current.deleteNodes("interval");
      });

      // Verify v2Properties were cleaned up
      expect(result.current.v2Properties).not.toHaveProperty("interval");
    });
  });

  describe("onConnect", () => {
    it("should allow connection from switch node to multiple targets", () => {
      const { result } = renderHook(() => useWorkflowStore());

      // Setup initial state with switch node
      act(() => {
        result.current.setNodes([
          {
            id: "switch1",
            data: { componentType: "switch", type: "condition-threshold" },
            position: { x: 0, y: 0 },
            isNested: false,
          } as FlowNode,
          {
            id: "target1",
            data: { type: "step" },
            position: { x: 100, y: 0 },
            isNested: false,
          } as FlowNode,
          {
            id: "target2",
            data: { type: "step" },
            position: { x: 100, y: 100 },
            isNested: false,
          } as FlowNode,
        ]);
      });

      // Connect switch to first target
      act(() => {
        result.current.onConnect({
          source: "switch1",
          target: "target1",
          sourceHandle: "source",
          targetHandle: "target",
        } as Connection);
      });

      // Connect switch to second target
      act(() => {
        result.current.onConnect({
          source: "switch1",
          target: "target2",
          sourceHandle: "source",
          targetHandle: "target",
        } as Connection);
      });

      // Verify both connections were allowed
      expect(result.current.edges).toHaveLength(2);
    });

    it("should only allow one connection from regular nodes", () => {
      const { result } = renderHook(() => useWorkflowStore());

      // Setup initial state
      act(() => {
        result.current.setNodes([
          {
            id: "node1",
            data: { type: "step" },
            position: { x: 0, y: 0 },
            isNested: false,
          } as FlowNode,
          {
            id: "target1",
            data: { type: "step" },
            position: { x: 100, y: 0 },
            isNested: false,
          } as FlowNode,
          {
            id: "target2",
            data: { type: "step" },
            position: { x: 100, y: 100 },
            isNested: false,
          } as FlowNode,
        ]);
      });

      // Make first connection
      act(() => {
        result.current.onConnect({
          source: "node1",
          target: "target1",
          sourceHandle: "source",
          targetHandle: "target",
        } as Connection);
      });

      // Try to make second connection
      act(() => {
        result.current.onConnect({
          source: "node1",
          target: "target2",
          sourceHandle: "source",
          targetHandle: "target",
        } as Connection);
      });

      // Verify only first connection exists
      expect(result.current.edges).toHaveLength(1);
      expect(result.current.edges[0].target).toBe("target1");
    });
  });

  describe("updateSelectedNodeData", () => {
    it("should update data for selected node", () => {
      const { result } = renderHook(() => useWorkflowStore());

      // Setup initial state
      act(() => {
        result.current.setNodes([
          {
            id: "node1",
            data: {
              type: "step",
              componentType: "task",
              properties: { config: "old-config" },
            },
            position: { x: 0, y: 0 },
            isNested: false,
          } as FlowNode,
        ]);
        result.current.setSelectedNode("node1");
      });

      // Update node data
      act(() => {
        result.current.updateSelectedNodeData("config", "new-config");
      });

      // Verify data was updated
      expect(result.current.nodes[0].data.config).toBe("new-config");
      expect(result.current.changes).toBe(1);
    });

    it("should remove property when value is null", () => {
      const { result } = renderHook(() => useWorkflowStore());

      // Setup initial state
      act(() => {
        result.current.setNodes([
          {
            id: "node1",
            data: {
              type: "step",
              componentType: "task",
              properties: {
                config: "old-config",
              },
            },
            position: { x: 0, y: 0 },
            isNested: false,
          } as FlowNode,
        ]);
        result.current.setSelectedNode("node1");
      });

      // Update node data with null
      act(() => {
        result.current.updateSelectedNodeData("config", null);
      });

      // Verify property was removed
      expect(result.current.nodes[0].data).not.toHaveProperty("config");
    });
  });

  describe("updateDefinition", () => {
    it("should validate a correct workflow without errors", () => {
      const { result } = renderHook(() => useWorkflowStore());

      // Setup a valid workflow definition
      act(() => {
        result.current.setDefinition({
          value: {
            sequence: [
              {
                id: "step1",
                name: "Step 1",
                type: "step-mock",
                componentType: "task",
                properties: {
                  stepParams: ["param1"],
                  config: "test",
                  with: {
                    param1: "value1",
                  },
                },
              },
            ],
            properties: {
              id: "test",
              disabled: false,
              name: "test",
              description: "test",
              manual: "true",
              isLocked: false,
              consts: {},
            },
          },
          isValid: true,
        });
        result.current.initializeWorkflow(null, mockProvidersConfiguration);
      });

      // Verify no validation errors and canDeploy is true
      expect(result.current.validationErrors).toEqual({});
      expect(result.current.canDeploy).toBe(true);
    });

    it("should capture validation errors for an invalid workflow", () => {
      const { result } = renderHook(() => useWorkflowStore());

      // Setup an invalid workflow definition
      act(() => {
        result.current.setDefinition({
          value: {
            sequence: [],
            // @ts-ignore
            properties: {},
          },
          isValid: false,
        });
        result.current.initializeWorkflow(null, mockProvidersConfiguration);
      });

      // Verify validation errors are captured
      expect(result.current.validationErrors).not.toEqual({});
      expect(result.current.validationErrors).toHaveProperty("workflow_name");
      expect(result.current.validationErrors).toHaveProperty(
        "workflow_description"
      );
      expect(result.current.canDeploy).toBe(false);
    });

    it("should validate each step and capture errors", () => {
      const { result } = renderHook(() => useWorkflowStore());

      // Setup a workflow with an invalid step
      act(() => {
        result.current.setDefinition({
          value: {
            sequence: [
              {
                id: "step1",
                name: "step1",
                type: "step-mock",
                componentType: "task",
                properties: {
                  stepParams: [],
                },
              },
              {
                id: "step2",
                name: "",
                type: "step-uninstalled",
                componentType: "task",
                properties: {
                  stepParams: [],
                },
              },
            ],
            properties: {
              id: "test",
              disabled: false,
              name: "test",
              description: "test",
              manual: "true",
              isLocked: false,
              consts: {},
            },
          },
          isValid: false,
        });
        result.current.initializeWorkflow(null, mockProvidersConfiguration);
      });

      // Verify step validation errors are captured
      expect(result.current.validationErrors).toHaveProperty("step1");
      expect(result.current.validationErrors["step1"]).toBe(
        "No parameters configured"
      );
      expect(result.current.validationErrors).toHaveProperty("step2");
      expect(result.current.validationErrors["step2"]).toBe(
        "Step name cannot be empty."
      );
    });

    it("should allow deployment if errors exist but are about missing providers", () => {
      const { result } = renderHook(() => useWorkflowStore());

      // Setup a workflow with provider-related errors
      act(() => {
        result.current.setDefinition({
          value: {
            sequence: [
              {
                id: "step1",
                name: "Step 1",
                type: "step-notinstalled",
                componentType: "task",
                properties: {
                  stepParams: ["param1"],
                  with: {
                    param1: "value1",
                  },
                },
              },
            ],
            properties: {
              id: "test",
              disabled: false,
              name: "test",
              description: "test",
              manual: "true",
              isLocked: false,
              consts: {},
            },
          },
          isValid: false,
        });
        result.current.initializeWorkflow(null, mockProvidersConfiguration);
      });

      // Verify canDeploy is true despite provider errors
      expect(result.current.validationErrors).not.toBe({});
      expect(result.current.canDeploy).toBe(true);
    });
  });
});
