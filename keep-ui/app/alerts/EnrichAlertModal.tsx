import { AlertDto } from "./models";
import Modal from "@/components/ui/Modal";
import { Button, TextInput, Divider } from "@tremor/react";
import { useSession } from "next-auth/react";
import { useApiUrl } from "utils/hooks/useConfig";
import React, { useEffect, useState } from "react";
import { toast } from "react-toastify";

interface EnrichAlertModalProps {
  alert: AlertDto | null | undefined;
  handleClose: () => void;
  mutate: () => void;
}

const EXCLUDED_FIELDS = [
  "id",
  "status",
  "severity",
  "lastReceived",
  "fingerprint",
  "isPartialDuplicate",
  "isFullDuplicate",
  "apiKeyRef",
  "firingStartTime",
  "enriched_fields",
  "isNoisy",
  "deleted",
  "startedAt",
  "incident",
  "providerId",
  "providerType",
  "dismissUntil",
  "dismissed",
  "assignee",
  "source",
  "pushed",
  "environment"
];

const transformAlertToEditableFields = (alert: AlertDto | null | undefined) => {
  if (!alert) return [];
  return Object.entries(alert)
    .filter(([key]) => !EXCLUDED_FIELDS.includes(key))
    .map(([key, value]) => ({ key, value }));
};

const EnrichAlertModal: React.FC<EnrichAlertModalProps> = ({
  alert,
  handleClose,
  mutate,
}) => {
  const isOpen = !!alert;
  const { data: session } = useSession();
  const apiUrl = useApiUrl();

  const [customFields, setCustomFields] = useState<{ key: string; value: string }[]>([]);
  const [editedFields, setEditedFields] = useState<{ key: string; value: string }[]>([]);
  const [finalData, setFinalData] = useState<Record<string, any>>({});

  const addCustomField = () => {
    setCustomFields((prev) => [...prev, { key: "", value: "" }]);
  };

  const updateCustomField = (index: number, field: "key" | "value", value: string) => {
    setCustomFields((prev) =>
      prev.map((item, i) => (i === index ? { ...item, [field]: value } : item))
    );
  };

  const removeCustomField = (index: number) => {
    setCustomFields((prev) => prev.filter((_, i) => i !== index));
  };

  const handleFieldChange = (key: string, value: string) => {
    setEditedFields((prev) =>
      prev.map((item) => (item.key === key ? { ...item, value } : item))
    );
  };

  useEffect(() => {
    setCustomFields([]);
    setEditedFields(transformAlertToEditableFields(alert));
  }, [alert]);

  useEffect(() => {
    const calculateFinalData = () => {
      const changedFields = editedFields.reduce((acc, field) => {
        const key = field.key as keyof AlertDto;
        const originalValue = alert ? alert[key] : undefined;

        if (String(originalValue) !== String(field.value)) {
          acc[key] = field.value as any ?? null;
        }
        return acc;
      }, {} as Partial<AlertDto>);

      const customFieldData = customFields.reduce((acc, field) => {
        if (field.key) {
          acc[field.key] = field.value;
        }
        return acc;
      }, {} as Record<string, string>);

      return { ...changedFields, ...customFieldData };
    };

    setFinalData(calculateFinalData());
  }, [customFields, editedFields, alert]);

  const handleSave = async () => {
    const requestData = {
      enrichments: finalData,
      fingerprint: alert?.fingerprint,
    };

    const response = await fetch(`${apiUrl}/alerts/enrich`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${session?.accessToken}`,
      },
      body: JSON.stringify(requestData),
    });

    if (response.ok) {
      toast.success("Alert enriched successfully");
      mutate();
      handleClose();
    } else {
      toast.error("Failed to enrich alert");
    }
  };

  const renderFormFields = () =>
    editedFields.map((field) => (
      <div key={field.key} className="mb-4 flex items-center gap-2">
        <label htmlFor={field.key} className="mb-1 w-[20%] truncate">
          {field.key}:
        </label>
        <TextInput
          id={field.key}
          name={field.key}
          value={String(field.value || "")}
          className="mt-1 w-full"
          onChange={(e) => handleFieldChange(e.target.name, e.target.value)}
        />
      </div>
    ));

  const renderCustomFields = () =>
    customFields.map((field, index) => (
      <div key={index} className="mb-4 flex items-center gap-2">
        <TextInput
          placeholder="Field Name"
          value={field.key}
          onChange={(e) => updateCustomField(index, "key", e.target.value)}
          required
          className="w-1/3"
        />
        <TextInput
          placeholder="Field Value"
          value={field.value}
          onChange={(e) => updateCustomField(index, "value", e.target.value)}
          className="w-1/3"
        />
        <Button color="red" onClick={() => removeCustomField(index)}>
          ✕
        </Button>
      </div>
    ));

  return (
    <Modal
      onClose={handleClose}
      isOpen={isOpen}
      className="overflow-auto !max-w-full w-[50%]"
    >
      <div className="flex justify-between items-center mb-4 min-w-full">
        <h2 className="text-lg font-semibold">Enrich Alert</h2>
        <div className="flex gap-x-2">
          <Button
            onClick={handleSave}
            color="orange"
            variant="primary"
            disabled={Object.keys(finalData).length === 0} // Disable button if finalData is empty
          >
            Save
          </Button>
          <Button onClick={handleClose} color="orange" variant="secondary">
            Close
          </Button>
        </div>
      </div>

      <div>
        <h3 className="text-md font-semibold mb-2">Custom Fields</h3>
        {renderCustomFields()}
        <Button onClick={addCustomField} className="mt-2 bg-orange-500">
          + Add Field
        </Button>
      </div>

      <Divider />

      <div>
        <h3 className="text-md font-semibold mb-2">Alert Data</h3>
        {alert ? renderFormFields() : <p>No data available.</p>}
      </div>
    </Modal>
  );
};

export default EnrichAlertModal;
