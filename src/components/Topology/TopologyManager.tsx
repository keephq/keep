import React, { useState } from "react";
import { TopologyGraph } from "./TopologyGraph";
import { TopologyService } from "../../services/TopologyService";
import { Button, Dialog, TextField, Select, MenuItem } from "@mui/material";

export const TopologyManager: React.FC = () => {
  const [isAddNodeDialogOpen, setAddNodeDialogOpen] = useState(false);
  const [newNode, setNewNode] = useState({
    name: "",
    type: "service",
    metadata: {},
  });

  const topologyService = new TopologyService();

  const handleAddNode = async () => {
    await topologyService.addNode({
      name: newNode.name,
      type: newNode.type as any,
      metadata: newNode.metadata,
      isEditable: true,
    });
    setAddNodeDialogOpen(false);
    setNewNode({ name: "", type: "service", metadata: {} });
  };

  return (
    <div>
      <div className="topology-toolbar">
        <Button variant="contained" onClick={() => setAddNodeDialogOpen(true)}>
          Add Service
        </Button>
      </div>

      <TopologyGraph topologyService={topologyService} />

      <Dialog
        open={isAddNodeDialogOpen}
        onClose={() => setAddNodeDialogOpen(false)}
      >
        <div className="dialog-content">
          <TextField
            label="Service Name"
            value={newNode.name}
            onChange={(e) => setNewNode({ ...newNode, name: e.target.value })}
          />
          <Select
            value={newNode.type}
            onChange={(e) => setNewNode({ ...newNode, type: e.target.value })}
          >
            <MenuItem value="service">Service</MenuItem>
            <MenuItem value="database">Database</MenuItem>
            <MenuItem value="cache">Cache</MenuItem>
            <MenuItem value="queue">Queue</MenuItem>
            <MenuItem value="external">External Service</MenuItem>
          </Select>
          <Button onClick={handleAddNode}>Add</Button>
        </div>
      </Dialog>
    </div>
  );
};
