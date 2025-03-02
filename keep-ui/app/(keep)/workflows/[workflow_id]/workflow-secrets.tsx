import React, { useState, useEffect } from "react";
import { Card } from "@tremor/react";
import { PlusIcon, TrashIcon } from "@heroicons/react/24/outline";
import { EyeOff, Eye } from 'lucide-react';
import { GenericTable } from "@/components/table/GenericTable";
import { DisplayColumnDef } from "@tanstack/react-table";
import { useSecrets } from "@/utils/hooks/useWorkFlowSecrets";

interface Secret {
  name: string;
  value: string;
}

const WorkflowSecrets = ({ workflowId }: { workflowId: string }) => {
  const { secrets, error, addOrUpdateSecret, deleteSecret } = useSecrets(workflowId);
  const [newSecret, setNewSecret] = useState({ name: "", value: "" });
  const [showValues, setShowValues] = useState<Record<string, boolean>>({});
  const [secretsArray, setSecretsArray] = useState<Secret[]>([]);

  useEffect(() => {
    setSecretsArray(Object.entries(secrets).map(([name, value]) => ({ name, value })));
  }, [secrets]);

  const handleAddSecret = async () => {
    if (!newSecret.name || !newSecret.value) return;
    await addOrUpdateSecret(newSecret.name, newSecret.value);
    setNewSecret({ name: "", value: "" });
  };

  const handleDeleteSecret = async (secretName: string) => {
    const confirmed = window.confirm(`Are you sure you want to delete the secret "${secretName}"?`);
    if (!confirmed) return;
    await deleteSecret(secretName);
  };

  const toggleShowValue = (secretName: string) => {
    setShowValues((prev) => ({
      ...prev,
      [secretName]: !prev[secretName],
    }));
  };

  const columns: DisplayColumnDef<Secret>[] = [
    {
      id: "name",
      header: "Name",
      cell: ({ row }) => (
        <code className="bg-gray-100 px-2 py-1 rounded">{`{{ secrets.${row.original.name} }}`}</code>
      ),
    },
    {
      id: "value",
      header: "Value",
      cell: ({ row }) => (
        <div className="flex items-center gap-2">
          {showValues[row.original.name] ? row.original.value : "••••••••"}
          <button
            onClick={() => toggleShowValue(row.original.name)}
            className="p-1 hover:bg-gray-100 rounded"
          >
            {showValues[row.original.name] ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
          </button>
        </div>
      ),
    },
    {
      id: "actions",
      header: "Actions",
      cell: ({ row }) => (
        <div className="flex gap-2">
          <button
            onClick={() => handleDeleteSecret(row.original.name)}
            className="p-1 hover:bg-gray-100 rounded"
          >
            <TrashIcon className="w-4 h-4 text-red-500" />
          </button>
        </div>
      ),
    },
  ];

  return (
    <Card className="p-4">
      <h2 className="text-xl font-semibold">Workflow Secrets</h2>

      {error && <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">{error}</div>}

      <div className="flex gap-4 my-4">
        <input
          type="text"
          placeholder="Secret name"
          value={newSecret.name}
          onChange={(e) => setNewSecret((prev) => ({ ...prev, name: e.target.value }))}
          className="flex-1 border rounded px-3 py-2"
        />
        <input
          type="password"
          placeholder="Secret value"
          value={newSecret.value}
          onChange={(e) => setNewSecret((prev) => ({ ...prev, value: e.target.value }))}
          className="flex-1 border rounded px-3 py-2"
        />
        <button
          onClick={handleAddSecret}
          className="flex items-center gap-2 bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600"
        >
          <PlusIcon className="w-4 h-4" />
          Add Secret
        </button>
      </div>

      <GenericTable
        data={secretsArray}
        columns={columns}
        rowCount={secretsArray.length}
        offset={0}
        limit={10}
        onPaginationChange={(newOffset, newLimit) => {
          console.log("Pagination changed:", newOffset, newLimit);
        }}
        dataFetchedAtOneGO={true}
      />
    </Card>
  );
};

export default WorkflowSecrets;
