import { act } from "@testing-library/react";
import { useWorkflowStore } from "../workflow-store";

const testWorkflow = `
workflow:
  id: console-example
  name: console-example
  description: console-example
  disabled: false
  triggers:
    - type: manual
  consts: {}
  owners: []
  services: []
  steps: []
  actions:
    - name: echo
      provider:
        config: "{{ providers.default-console }}"
        type: console
        with:
          logger: true
          message: Hey
`;

describe("WorkflowStore", () => {
  beforeEach(() => {
    const store = useWorkflowStore.getState();
    store.initialize(testWorkflow, [], "test-workflow");
  });

  it("should update definition before saving", async () => {
    const updates: string[] = [];

    // Mock save function to track when it's called
    useWorkflowStore.setState({
      selectedNode: useWorkflowStore
        .getState()
        .nodes.find((node) => node.data.name === "echo")?.id,
      saveWorkflow: async () => {
        const def = useWorkflowStore.getState().definition;
        updates.push(`save:${def.value.sequence?.[0]?.name}`);
      },
    });

    // Track definition updates
    const unsub = useWorkflowStore.subscribe((state, prevState) => {
      if (
        state.definition.value.sequence[0]?.name !==
        prevState.definition.value.sequence[0]?.name
      ) {
        updates.push(`def:${state.definition.value.sequence[0].name}`);
      }
    });

    // Simulate editor submit
    await act(async () => {
      const store = useWorkflowStore.getState();
      store.updateSelectedNodeData("name", "new-name");
      await store.saveWorkflow();
    });

    unsub();

    // Check update sequence
    expect(updates).toEqual([
      "def:new-name", // Definition updated with new name
      "save:new-name", // Save called with updated definition
    ]);
  });
});
