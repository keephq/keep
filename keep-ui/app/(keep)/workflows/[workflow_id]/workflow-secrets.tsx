import React, { useState, useEffect } from "react";
import { Card } from "@tremor/react";
import { PlusIcon, TrashIcon, EyeIcon, EyeOffIcon } from "@heroicons/react/24/outline";
import { GenericTable } from "@/components/table/GenericTable";
import { DisplayColumnDef } from "@tanstack/react-table";
import { useSecrets } from "@/utils/hooks/useWorkFlowSecrets"; 

interface Secret {
  name: string;
  value: string;
}

const WorkflowSecrets = ({ workflowId }: { workflowId: string }) => {
  const { secrets, error, addOrUpdateSecret, readSecret, deleteSecret } = useSecrets(workflowId);
  const [newSecret, setNewSecret] = useState({ name: "", value: "" });
  const [showValues, setShowValues] = useState<Record<string, boolean>>({});

  const handleAddSecret = async () => {
    if (!newSecret.name || !newSecret.value) return;
    await addOrUpdateSecret(newSecret.name, newSecret.value);
    setNewSecret({ name: "", value: "" }); 
  };

  const handleDeleteSecret = async (secretName: string) => {
    await deleteSecret(secretName);
  };

  const toggleShowValue = async (secretName: string) => {
    if (!showValues[secretName]) {
      const secretValue = await readSecret(secretName);
      if (secretValue) {
        setShowValues((prev) => ({ ...prev, [secretName]: true }));
      }
    } else {
      setShowValues((prev) => ({ ...prev, [secretName]: false }));
    }
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
        </div>
      ),
    },
    {
      id: "actions",
      header: "Actions",
      cell: ({ row }) => (
        <div className="flex gap-2">
          <button
            onClick={() => toggleShowValue(row.original.name)}
            className="p-1 hover:bg-gray-100 rounded"
          >
            {showValues[row.original.name] ? <EyeOffIcon className="w-4 h-4" /> : <EyeIcon className="w-4 h-4" />}
          </button>
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
        data={secrets}
        columns={columns}
        rowCount={secrets.length}
        offset={0}
        limit={10}
        onPaginationChange={() => {}}
        dataFetchedAtOneGO={true}
      />
    </Card>
  );
};

export default WorkflowSecrets;
