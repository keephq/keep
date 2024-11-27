import { AlertDto } from "./models";
import { Dialog, Transition } from "@headlessui/react";
import React, { Fragment, useEffect, useState } from "react";
import { Button, TextInput } from "@tremor/react";
import { toast } from "react-toastify";
import SidePanel from "@/components/SidePanel";
import { showErrorToast } from "@/shared/ui/utils/showErrorToast";
import { useApi } from "@/shared/lib/hooks/useApi";

interface EnrichAlertModalProps {
  alert: AlertDto | null | undefined;
  isOpen: boolean;
  handleClose: () => void;
  mutate: () => void;
}

const EnrichAlertSidePanel: React.FC<EnrichAlertModalProps> = ({
  alert,
  isOpen,
  handleClose,
  mutate,
}) => {
  const api = useApi();

  const [customFields, setCustomFields] = useState<
    { key: string; value: string }[]
  >([]);

  const [preEnrichedFields, setPreEnrichedFields] = useState<
    { key: string; value: string }[]
  >([]);

  const [finalData, setFinalData] = useState<Record<string, any>>({});
  const [isDataValid, setIsDataValid] = useState<boolean>(false);

  const addCustomField = () => {
    setCustomFields((prev) => [...prev, { key: "", value: "" }]);
  };

  const updateCustomField = (
    index: number,
    field: "key" | "value",
    value: string
  ) => {
    setCustomFields((prev) =>
      prev.map((item, i) => (i === index ? { ...item, [field]: value } : item))
    );
  };

  const removeCustomField = (index: number) => {
    setCustomFields((prev) => prev.filter((_, i) => i !== index));
  };

  useEffect(() => {
    const preEnrichedFields =
      alert?.enriched_fields?.map((key) => {
        return { key, value: alert[key as keyof AlertDto] as any };
      }) || [];
    setCustomFields(preEnrichedFields);
    setPreEnrichedFields(preEnrichedFields);
  }, [alert]);

  useEffect(() => {
    const validateData = () => {
      const areFieldsIdentical =
        customFields.length === preEnrichedFields.length &&
        customFields.every((field) => {
          const matchingField = preEnrichedFields.find(
            (preField) => preField.key === field.key
          );
          return matchingField && matchingField.value === field.value;
        });

      if (areFieldsIdentical) {
        setIsDataValid(false);
        return;
      }

      const keys = customFields.map((field) => field.key);
      const hasEmptyKeys = keys.some((key) => !key);
      const hasDuplicateKeys = new Set(keys).size !== keys.length;

      setIsDataValid(!hasEmptyKeys && !hasDuplicateKeys);
    };

    const calculateFinalData = () => {
      return customFields.reduce(
        (acc, field) => {
          if (field.key) {
            acc[field.key] = field.value;
          }
          return acc;
        },
        {} as Record<string, string>
      );
    };
    setFinalData(calculateFinalData());
    validateData();
  }, [customFields, preEnrichedFields]);

  useEffect(() => {
    if (!isOpen) {
      setFinalData({});
      setIsDataValid(false);
    }
  }, [isOpen]);

  const handleSave = async () => {
    const requestData = {
      enrichments: finalData,
      fingerprint: alert?.fingerprint,
    };

    const enrichedFieldKeys = customFields.map((field) => field.key);
    const preEnrichedFieldKeys = preEnrichedFields.map((field) => field.key);

    const unEnrichedFields = preEnrichedFieldKeys.filter((key) => {
      if (!enrichedFieldKeys.includes(key)) {
        return key;
      }
    });

    let fieldsUnEnrichedSuccessfully = unEnrichedFields.length === 0;

    try {
      if (unEnrichedFields.length != 0) {
        const unEnrichmentResponse = await api.post("/alerts/unenrich", {
          fingerprint: alert?.fingerprint,
          enrichments: unEnrichedFields,
        });
        fieldsUnEnrichedSuccessfully = true;
      }

      const response = await api.post("/alerts/enrich", requestData);

      toast.success("Alert enriched successfully");
      await mutate();
      handleClose();
    } catch (error) {
      showErrorToast(error, "Failed to enrich alert");
    }
  };

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
          className="w-full"
        />
        <Button color="red" onClick={() => removeCustomField(index)}>
          ✕
        </Button>
      </div>
    ));

  return (
    <SidePanel isOpen={isOpen} onClose={handleClose} panelWidth={"w-1/3"}>
      <div className="flex justify-between items-center min-w-full">
        <h2 className="text-lg font-semibold">Enrich Alert</h2>
      </div>

      <div className="flex-1 overflow-auto pb-6 mt-4">
        {renderCustomFields()}
      </div>

      <div className="sticky bottom-0 p-4 border-t border-gray-200 bg-white flex justify-end gap-2">
        <Button
          onClick={addCustomField}
          className="bg-orange-500"
          variant="primary"
        >
          + Add Field
        </Button>
        <Button
          onClick={handleSave}
          color="orange"
          variant="primary"
          disabled={!isDataValid}
        >
          Save
        </Button>
        <Button onClick={handleClose} color="orange" variant="secondary">
          Close
        </Button>
      </div>
    </SidePanel>
  );
};

export default EnrichAlertSidePanel;
