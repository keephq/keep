import { v4 as uuidv4 } from "uuid";
import { FlowNode, V2Step } from "app/workflows/builder/builder-store";
import { Edge } from "@xyflow/react";



export function createSwitchNodeV2(
    step: any,
    nodeId: string,
    position: { x: number; y: number },
    nextNodeId?: string | null,
    prevNodeId?: string | null
): FlowNode[] {
    const customIdentifier = `${step.type}__end__${nodeId}`;
    return [
        {
            id: nodeId,
            type: "custom",
            position: { x: 0, y: 0 },
            data: {
                label: step.name,
                ...step,
            },
            isDraggable: false,
            prevNodeId,
            nextNodeId: customIdentifier,
            dragHandle: ".custom-drag-handle",
            style: {
                margin: "0px 20px 0px 20px",
            }
        },
        {
            id: customIdentifier,
            type: "custom",
            position: { x: 0, y: 0 },
            data: {
                label: "+",
                id: customIdentifier,
                type: `${step.type}__end_node`,
            },
            isDraggable: false,
            prevNodeId: nodeId,
            nextNodeId: nextNodeId,
            dragHandle: ".custom-drag-handle",
        },
    ];
};



export function handleSwitchNode(step, position, nextNodeId, prevNodeId, nodeId) {
    if (step.componentType !== "switch") {
        return { nodes: [], edges: [] };
    }
    let trueBranches = step?.branches?.true || [];
    let falseBranches = step?.branches?.false || [];


    function _getEmptyNode(type: string) {
        const key = `empty_${type}`
        return {
            id: `${step.type}__${nodeId}__${key}`,
            type: key,
            componentType: key,
            name: "empty",
            properties: {},
        }
    }

    let [switchStartNode, switchEndNode] = createSwitchNodeV2(step, nodeId, position, nextNodeId, prevNodeId);
    trueBranches = [
        { ...switchStartNode.data, type: 'temp_node', componentType: "temp_node" },
        ...trueBranches,
        _getEmptyNode("true"),
        { ...switchEndNode.data, type: 'temp_node', componentType: "temp_node" }
    ];
    falseBranches = [
        { ...switchStartNode.data, type: 'temp_node', componentType: "temp_node" },
        ...falseBranches,
        _getEmptyNode("false"),
        { ...switchEndNode.data, type: 'temp_node', componentType: "temp_node" }
    ]

    let truePostion = { x: position.x - 200, y: position.y - 100 };
    let falsePostion = { x: position.x + 200, y: position.y - 100 };

    let { nodes: trueBranchNodes, edges: trueSubflowEdges } =
        processWorkflowV2(trueBranches, truePostion) || {};
    let { nodes: falseSubflowNodes, edges: falseSubflowEdges } =
        processWorkflowV2(falseBranches, falsePostion) || {};

    function _adjustEdgeConnectionsAndLabelsForSwitch(type: string) {
        if (!type) {
            return;
        }
        const subflowEdges = type === 'True' ? trueSubflowEdges : falseSubflowEdges;
        const subflowNodes = type === 'True' ? trueBranchNodes : falseSubflowNodes;
        const [firstEdge] = subflowEdges;
        firstEdge.label = type?.toString();
        firstEdge.id = `e${switchStartNode.prevNodeId}-${firstEdge.target || switchEndNode.id
            }`;
        firstEdge.source = switchStartNode.id || "";
        firstEdge.target = firstEdge.target || switchEndNode.id;
        subflowEdges.pop();
    }
    _adjustEdgeConnectionsAndLabelsForSwitch('True');
    _adjustEdgeConnectionsAndLabelsForSwitch('False');
    return {
        nodes: [
            switchStartNode,
            ...trueBranchNodes,
            ...falseSubflowNodes,
            switchEndNode,
        ], edges: [
            ...trueSubflowEdges,
            ...falseSubflowEdges,
            //handling the switch end edge
            createCustomEdgeMeta(switchEndNode.id, nextNodeId)
        ]
    };

}

export const createDefaultNodeV2 = (
    step: any,
    nodeId: string,
    position: { x: number; y: number },
    nextNodeId?: string | null,
    prevNodeId?: string | null
): FlowNode =>
({
    id: nodeId,
    type: "custom",
    dragHandle: ".custom-drag-handle",
    position: { x: 0, y: 0 },
    data: {
        label: step.name,
        ...step,
    },
    isDraggable: false,
    nextNodeId,
    prevNodeId,
} as FlowNode);

const getRandomColor = () => {
    const letters = '0123456789ABCDEF';
    let color = '#';
    for (let i = 0; i < 6; i++) {
        color += letters[Math.floor(Math.random() * 16)];
    }
    return color;
};

export function createCustomEdgeMeta(source: string, target: string, label?: string, color?: string, type?: string) {
    return {
        id: `e${source}-${target}`,
        source: source ?? "",
        target: target ?? "",
        type: type || "custom-edge",
        label,
        style: { stroke: color || getRandomColor() }
    }
}
export function handleDefaultNode(step, position, nextNodeId, prevNodeId, nodeId) {
    const nodes = [];
    const edges = [];
    const newNode = createDefaultNodeV2(
        step,
        nodeId,
        position,
        nextNodeId,
        prevNodeId
    );
    if (step.type !== 'temp_node') {
        nodes.push(newNode);
    }
    // Handle edge for default nodes
    if (newNode.id !== "end" && !step.edgeNotNeeded) {
        edges.push(createCustomEdgeMeta(newNode.id, nextNodeId, step.edgeLabel, step.edgeColor));
    }
    return { nodes, edges };
}

export function getForEachNode(step, position, nodeId, prevNodeId, nextNodeId, parents = []) {
    const { sequence, ...rest } = step;
    const customIdentifier = `${step.type}__end__${nodeId}`;

    return [
        {
            id: nodeId,
            data: { ...rest, id: nodeId },
            type: "custom",
            position: { x: 0, y: 0 },
            isDraggable: false,
            dragHandle: ".custom-drag-handle",
            prevNodeId: prevNodeId,
            nextNodeId: nextNodeId
        },
        {
            id: customIdentifier,
            data: { ...rest, id: customIdentifier, name: "foreach end", label: "foreach end" },
            type: "custom",
            position: { x: 0, y: 0 },
            isDraggable: false,
            dragHandle: ".custom-drag-handle",
            prevNodeId: prevNodeId,
            nextNodeId: nextNodeId,
        },
    ];
}


export function handleForeachNode(step, position, nextNodeId, prevNodeId, nodeId) {

    const [forEachStartNode, forEachEndNode] = getForEachNode(step, position, nodeId, prevNodeId, nextNodeId);

    function _getEmptyNode(type: string) {
        const key = `empty_${type}`
        return {
            id: `${step.type}__${nodeId}__${key}`,
            type: key,
            componentType: key,
            name: "empty",
            properties: {},
            parents: [nodeId]
        }
    }
    const sequences = [
        { id: prevNodeId, type: "temp_node", componentType: "temp_node", name: "temp_node", properties: {}, edgeNotNeeded: true },
        { id: forEachStartNode.id, type: "temp_node", componentType: "temp_node", name: "temp_node", properties: {} },
        ...step.sequence,
        _getEmptyNode("foreach"),
        { id: forEachEndNode.id, type: "temp_node", componentType: "temp_node", name: "temp_node", properties: {} },
        { id: nextNodeId, type: "temp_node", componentType: "temp_node", name: "temp_node", properties: {}, edgeNotNeeded: true },
    ];
    const { nodes, edges } = processWorkflowV2(sequences, position);
    return { nodes: [forEachStartNode, ...nodes, forEachEndNode], edges: edges };
}


export const processStepV2 = (
    step: any,
    position: { x: number; y: number },
    nextNodeId?: string | null,
    prevNodeId?: string | null,
) => {
    const nodeId = step.id;
    let newNodes: FlowNode[] = [];
    let newEdges: Edge[] = [];
    switch (true) {
        case step?.componentType === "switch":
            {
                const { nodes, edges } = handleSwitchNode(step, position, nextNodeId, prevNodeId, nodeId);
                newEdges = [...newEdges, ...edges];
                newNodes = [...newNodes, ...nodes];
                break;
            }
        case step?.componentType === "container" && step?.type === "foreach":
            {
                const { nodes, edges } = handleForeachNode(step, position, nextNodeId, prevNodeId, nodeId);
                newEdges = [...newEdges, ...edges];
                newNodes = [...newNodes, ...nodes];
                break;
            }
        default:
            {
                const { nodes, edges } = handleDefaultNode(step, position, nextNodeId, prevNodeId, nodeId);
                newEdges = [...newEdges, ...edges];
                newNodes = [...newNodes, ...nodes];
                break;
            }
    }

    return { nodes: newNodes, edges: newEdges };
};

export const processWorkflowV2 = (sequence: any, position: { x: number, y: number }, isFirstRender = false) => {
    let newNodes: FlowNode[] = [];
    let newEdges: Edge[] = [];

    sequence?.forEach((step: any, index: number) => {
        const prevNodeId = sequence?.[index - 1]?.id || null;
        const nextNodeId = sequence?.[index + 1]?.id || null;
        position.y += 150;
        const { nodes, edges } = processStepV2(
            step,
            position,
            nextNodeId,
            prevNodeId
        );
        newNodes = [...newNodes, ...nodes];
        newEdges = [...newEdges, ...edges];
    });

    if (isFirstRender) {
        newNodes = newNodes.map((node) => ({ ...node, isLayouted: false }));
        newEdges = newEdges.map((edge) => ({ ...edge, isLayouted: false }));
    }
    return { nodes: newNodes, edges: newEdges };
};
