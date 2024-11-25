import { useState } from "react";
import Modal from "@/components/ui/Modal";
import { Button, TextInput } from "@tremor/react";
import { AlertsRulesBuilder } from "@/app/(keep)/alerts/alerts-rules-builder";
import { useHydratedSession as useSession } from "@/shared/lib/hooks/useHydratedSession";
import { useApiUrl } from "utils/hooks/useConfig";
import { useApi } from "@/shared/lib/hooks/useApi";

interface AlertTabModalProps {
  presetId: string;
  isOpen: boolean;
  onClose: () => void;
  onAddTab: (name: string, filter: string) => void;
}

const AlertTabModal = ({
  presetId,
  isOpen,
  onClose,
  onAddTab,
}: AlertTabModalProps) => {
  const [newTabName, setNewTabName] = useState("");
  const [newTabFilter, setNewTabFilter] = useState<string>("");
  const [errors, setErrors] = useState({ name: false, filter: false });
  const [backendError, setBackendError] = useState<string | null>(null);
  const api = useApi();
  const handleAddTab = async () => {
    if (!newTabName || !newTabFilter) {
      setErrors({
        name: !newTabName,
        filter: !newTabFilter,
      });
      return;
    }

    try {
      // Send the new tab data to the backend
      const response = await api.post(`/preset/${presetId}/tab`, {
        name: newTabName,
        filter: newTabFilter,
      });

      if (!response.ok) {
        throw new Error(
          "Failed to add the new tab: " +
            response.status +
            " " +
            response.statusText
        );
      }

      onAddTab(newTabName, newTabFilter);
      setNewTabName("");
      setNewTabFilter("");
      setBackendError(null); // Clear any previous backend errors
      onClose();
    } catch (error) {
      if (error instanceof Error) {
        setBackendError(error.message);
      } else {
        setBackendError("An error occurred while adding the tab");
      }
    }
  };

  const handleNameChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setNewTabName(e.target.value);
    if (errors.name && e.target.value) {
      setErrors((prev) => ({ ...prev, name: false }));
    }
  };

  const handleFilterChange = (value: any) => {
    setNewTabFilter(value);
    if (errors.filter && value) {
      setErrors((prev) => ({ ...prev, filter: false }));
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Create New Tab">
      <div className="space-y-8">
        <TextInput
          className="tremor-border-orange mt-4"
          value={newTabName}
          onChange={handleNameChange}
          placeholder="Tab Name"
          error={errors.name}
        />
        {errors.name && (
          <p className="text-red-500 text-sm">Tab name is required</p>
        )}
        <AlertsRulesBuilder
          defaultQuery=""
          updateOutputCEL={handleFilterChange}
          showSave={false}
          showSqlImport={false}
          minimal={true}
        />
        {errors.filter && (
          <p className="text-red-500 text-sm">Filter is required</p>
        )}
        {backendError && <p className="text-red-500 text-sm">{backendError}</p>}
        <Button
          disabled={!newTabName || !newTabFilter}
          color="orange"
          onClick={handleAddTab}
          className="mt-16"
          tooltip={
            !newTabName
              ? "Tab name is required"
              : !newTabFilter
                ? "Tab filter is required (notice you need to click 'enter' to apply the filter)"
                : ""
          }
        >
          Add Tab
        </Button>
      </div>
    </Modal>
  );
};

export default AlertTabModal;
