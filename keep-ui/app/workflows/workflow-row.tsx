import React from "react";
import { Table } from "@tremor/react";

export interface Workflow {
  id: string;
  description: string;
  owners: string[];
  services: string[];
  interval: number;
  steps: Step[];
  actions: Action[];
}

interface Step {
  name: string;
  provider: {
    type: string;
    config: string;
    with?: {
    };
  };
}

interface Action {
  name: string;
  condition: {
    name: string;
    type: string;
    value: string;
    compare_to: string;
  }[];
  provider: {
    type: string;
    config: string;
    with: {
    };
  };
}

interface WorkflowRowProps {
  workflow: Workflow;
}

const WorkflowRow: React.FC<WorkflowRowProps> = ({ workflow }) => {
  return (
    <tr>
      <td>{workflow.id}</td>
      <td>{workflow.description}</td>
      <td>{workflow.owners.join(', ')}</td>
      <td>{workflow.services.join(', ')}</td>
      <td>{workflow.interval}</td>
      <td>{workflow.steps.length}</td>
      <td>{workflow.actions.length}</td>
    </tr>
  );
};

export default WorkflowRow;
