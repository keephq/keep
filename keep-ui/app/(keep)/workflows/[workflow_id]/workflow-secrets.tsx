import React, { useState, useEffect } from "react";
import { Card } from "@tremor/react";
import { PlusIcon, TrashIcon } from "@heroicons/react/24/outline";
import { EyeOff, Eye } from "lucide-react";
import { GenericTable } from "@/components/table/GenericTable";
import { DisplayColumnDef } from "@tanstack/react-table";
import { useSecrets } from "@/utils/hooks/useWorkFlowSecrets";
import { Button } from "@/components/ui";
import { Input } from "@/shared/ui";

const WorkflowSecrets = ({ workflowId }: { workflowId: string }) => {
  const { getSecrets, error, addOrUpdateSecret, deleteSecret } =
    useSecrets(workflowId);
  const [newSecret, setNewSecret] = useState({ name: "", value: "" });
  const [showValues, setShowValues] = useState<Record<string, boolean>>({});
  const { data: secrets, mutate: mutateSecrets } = getSecrets;

  const handleAddSecret = async () => {
    if (!newSecret.name || !newSecret.value || !secrets) return;
    await addOrUpdateSecret(secrets, newSecret.name, newSecret.value);
    setNewSecret({ name: "", value: "" });
    mutateSecrets();
  };

  const handleDeleteSecret = async (secretName: string) => {
    const confirmed = window.confirm(
      `Are you sure you want to delete the secret "${secretName}"?`
    );
    if (!confirmed) return;
    await deleteSecret(secretName);
    mutateSecrets();
  };

  const toggleShowValue = (secretName: string) => {
    setShowValues((prev) => ({
      ...prev,
      [secretName]: !prev[secretName],
    }));
  };

  const columns: DisplayColumnDef<{ name: string; value: string }>[] = [
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
          <div
            className="w-96 overflow-hidden text-ellipsis whitespace-nowrap"
            title={showValues[row.original.name] ? row.original.value : ""}
          >
            {showValues[row.original.name] ? row.original.value : "••••••••"}
          </div>
          <Button
            onClick={() => toggleShowValue(row.original.name)}
            className="p-1 hover:bg-gray-100 rounded"
            icon={showValues[row.original.name] ? EyeOff : Eye}
            variant="secondary"
          />
        </div>
      ),
    },
    {
      id: "actions",
      header: "Actions",
      cell: ({ row }) => (
        <div className="flex gap-2">
          <Button
            variant="secondary"
            onClick={() => handleDeleteSecret(row.original.name)}
            className="p-1 hover:bg-gray-100"
            icon={TrashIcon}
            color="red"
          />
        </div>
      ),
    },
  ];

  return (
    <Card className="p-4">
      <h2 className="text-xl font-semibold">Workflow Secrets</h2>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
          {error}
        </div>
      )}

      <div className="flex gap-4 my-4">
        <Input
          type="text"
          placeholder="Secret name"
          value={newSecret.name}
          onChange={(e) =>
            setNewSecret((prev) => ({ ...prev, name: e.target.value }))
          }
        />
        <Input
          placeholder="Secret value"
          value={newSecret.value}
          onChange={(e) =>
            setNewSecret((prev) => ({ ...prev, value: e.target.value }))
          }
        />
        <Button onClick={handleAddSecret} variant="primary" icon={PlusIcon}>
          Add Secret
        </Button>
      </div>

      <GenericTable
        data={
          secrets
            ? Object.entries(secrets).map(([name, value]) => ({ name, value }))
            : []
        }
        columns={columns}
        rowCount={secrets ? Object.keys(secrets).length : 0}
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
