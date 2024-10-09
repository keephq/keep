import React from "react";
import useStore from "./builder-store";
import { Button } from "@tremor/react";
import { reConstructWorklowToDefinition } from "utils/reactFlow";

export default function BuilderChanagesTracker({
  onDefinitionChange,
}: {
  onDefinitionChange: (def: Record<string, any>) => void;
}) {
  const {
    nodes,
    edges,
    setEdges,
    setNodes,
    isLayouted,
    setIsLayouted,
    v2Properties,
    changes,
    setChanges,
    lastSavedChanges,
    setLastSavedChanges,
  } = useStore();
  const handleDiscardChanges = (e: React.MouseEvent<HTMLButtonElement>) => {
    if (!isLayouted) return;
    setEdges(lastSavedChanges.edges || []);
    setNodes(lastSavedChanges.nodes || []);
    setChanges(0);
    setIsLayouted(false);
  };

  const handleSaveChanges = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setLastSavedChanges({ nodes: nodes, edges: edges });
    const value = reConstructWorklowToDefinition({
      nodes: nodes,
      edges: edges,
      properties: v2Properties,
    });
    onDefinitionChange(value);
    setChanges(0);
  };

  return (
    <div className="flex gap-2.5">
      <Button onClick={handleDiscardChanges} disabled={changes === 0}>
        Discard{changes ? `(${changes})` : ""}
      </Button>
      <Button onClick={handleSaveChanges} disabled={changes === 0}>
        Save
      </Button>
    </div>
  );
}
