import React from 'react';
import { Table } from '@tremor/react';
import WorkflowRow from './workflow-row'; // Replace with the path to the WorkflowRow component

export default function WorkflowsTable({ workflows }) {

  return (
    <Table>
      <thead>
        <tr>
          <th>ID</th>
          <th>Description</th>
          <th>Owners</th>
          <th>Services</th>
          <th>Interval</th>
          <th>Number of Steps</th>
          <th>Number of Actions</th>
        </tr>
      </thead>
      <tbody>
        {workflows
          .filter((workflow) => Object.keys(workflow.details).length > 0)
          .map((workflow) => (
            <WorkflowRow key={workflow.id} workflow={workflow} />
          ))}
      </tbody>
    </Table>
  );
}
