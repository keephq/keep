import { v4 as uuidv4 } from "uuid";
import { FlowNode, V2Step } from "app/workflows/builder/builder-store";
import { Edge } from "@xyflow/react";
import { CorrelationForm as CorrelationFormType } from '.';



function getKeyBasedSquence(step:any, id:string,  type:string) {
    return `${step.type}__${id}__empty_${type}`;
}

export function reConstructWorklowToDefinition({
    nodes,
    edges, isNested = false}:{
        nodes: FlowNode[],
        edges: Edge[]
        isNested?:boolean
    }) {
        const seuqences = [];
        //ingoring the start node
        const [first, ...rest] = nodes;
        //poping the end node
        rest.pop();
        const edgeMap: Record<string, string[]> = {};
        const nodeMap: Record<string, FlowNode> = {};
        edges.forEach((edge) => {
          const { source, target } = edge;
      
          if (edgeMap[source]) {
            edgeMap[source].push(target);
          } else {
            edgeMap[source] = [target];
          }
        });

        nodes.forEach((node) => {
          nodeMap[node.id] = node;
        });

        const sequences = nodes.filter((node) => !node.isNested && !node.id.includes('end')).map((node) => node.data);
        console.log("sequences in recontructWorklowToDefinition", sequences)

}

export function createSwitchNodeV2(
    step: any,
    nodeId: string,
    position: { x: number; y: number },
    nextNodeId?: string | null,
    prevNodeId?: string | null,
    isNested?: boolean,
): FlowNode[] {
    const customIdentifier = `${step.type}__end__${nodeId}`;
    const { name, type, componentType, properties} = step;
    return [
        {
            id: nodeId,
            type: "custom",
            position: { x: 0, y: 0 },
            data: {
                label: name,
                type,
                componentType,
                id: nodeId,
                properties,
            },
            isDraggable: false,
            prevNodeId,
            nextNodeId: customIdentifier,
            dragHandle: ".custom-drag-handle",
            style: {
                margin: "0px 20px 0px 20px",
            },
            isNested: !!isNested
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
            isNested: !!isNested
        },
    ];
};



export function handleSwitchNode(step, position, nextNodeId, prevNodeId, nodeId, isNested) {
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
            isNested: true,
        }
    }

    let [switchStartNode, switchEndNode] = createSwitchNodeV2(step, nodeId, position, nextNodeId, prevNodeId, isNested);
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
        processWorkflowV2(trueBranches, truePostion, false, true) || {};
    let { nodes: falseSubflowNodes, edges: falseSubflowEdges } =
        processWorkflowV2(falseBranches, falsePostion, false, true) || {};

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
    prevNodeId?: string | null,
    isNested?: boolean,
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
    isNested: !!isNested
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
export function handleDefaultNode(step, position, nextNodeId, prevNodeId, nodeId, isNested) {
    const nodes = [];
    const edges = [];
    const newNode = createDefaultNodeV2(
        step,
        nodeId,
        position,
        nextNodeId,
        prevNodeId,
        isNested
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

export function getForEachNode(step, position, nodeId, prevNodeId, nextNodeId, isNested) {
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
            nextNodeId: nextNodeId,
            isNested: !!isNested,
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
            isNested: !!isNested
        },
    ];
}


export function handleForeachNode(step, position, nextNodeId, prevNodeId, nodeId, isNested) {

    const [forEachStartNode, forEachEndNode] = getForEachNode(step, position, nodeId, prevNodeId, nextNodeId, isNested);

    function _getEmptyNode(type: string) {
        const key = `empty_${type}`
        return {
            id: `${step.type}__${nodeId}__${key}`,
            type: key,
            componentType: key,
            name: "empty",
            properties: {},
            isNested: true,
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
    const { nodes, edges } = processWorkflowV2(sequences, position, false, true);
    return { nodes: [forEachStartNode, ...nodes, forEachEndNode], edges: edges };
}


export const processStepV2 = (
    step: any,
    position: { x: number; y: number },
    nextNodeId?: string | null,
    prevNodeId?: string | null,
    isNested?: boolean
) => {
    const nodeId = step.id;
    let newNodes: FlowNode[] = [];
    let newEdges: Edge[] = [];
    switch (true) {
        case step?.componentType === "switch":
            {
                const { nodes, edges } = handleSwitchNode(step, position, nextNodeId, prevNodeId, nodeId, isNested);
                newEdges = [...newEdges, ...edges];
                newNodes = [...newNodes, ...nodes];
                break;
            }
        case step?.componentType === "container" && step?.type === "foreach":
            {
                const { nodes, edges } = handleForeachNode(step, position, nextNodeId, prevNodeId, nodeId, isNested);
                newEdges = [...newEdges, ...edges];
                newNodes = [...newNodes, ...nodes];
                break;
            }
        default:
            {
                const { nodes, edges } = handleDefaultNode(step, position, nextNodeId, prevNodeId, nodeId, isNested);
                newEdges = [...newEdges, ...edges];
                newNodes = [...newNodes, ...nodes];
                break;
            }
    }

    return { nodes: newNodes, edges: newEdges };
};

export const processWorkflowV2 = (sequence: any, position: { x: number, y: number }, isFirstRender = false, isNested = false) => {
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
            prevNodeId,
            isNested,
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
