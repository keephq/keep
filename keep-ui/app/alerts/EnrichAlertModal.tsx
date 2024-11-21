import { AlertDto } from "./models";
import Modal from "@/components/ui/Modal";
import "react-sliding-side-panel/lib/index.css";
import SlidingPanel from "react-sliding-side-panel";
import { Dialog, Transition } from "@headlessui/react";
import { Fragment } from "react";
import { Button, TextInput, Divider } from "@tremor/react";
import { useSession } from "next-auth/react";
import { useApiUrl } from "utils/hooks/useConfig";
import React, { useEffect, useState } from "react";
import { toast } from "react-toastify";
import { Alert } from "../workflows/builder/alert";

interface EnrichAlertModalProps {
  alert: AlertDto | null | undefined;
  isOpen: boolean;
  handleClose: () => void;
  mutate: () => void;
}

const EnrichAlertModal: React.FC<EnrichAlertModalProps> = ({
  alert,
  isOpen,
  handleClose,
  mutate,
}) => {
  const { data: session } = useSession();
  const apiUrl = useApiUrl();

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
      const customFieldData = customFields.reduce(
        (acc, field) => {
          if (field.key) {
            acc[field.key] = field.value;
          }
          return acc;
        },
        {} as Record<string, string>
      );

      return customFieldData;
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

    let fieldsUnenrichedSuccessfully = true;

    if (unEnrichedFields.length != 0) {
      const unerichmentResponse = await fetch(`${apiUrl}/alerts/unenrich`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session?.accessToken}`,
        },
        body: JSON.stringify({
          fingerprint: alert?.fingerprint,
          enrichments: unEnrichedFields,
        }),
      });
      fieldsUnenrichedSuccessfully = unerichmentResponse.ok;
    }

    const response = await fetch(`${apiUrl}/alerts/enrich`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${session?.accessToken}`,
      },
      body: JSON.stringify(requestData),
    });

    if (response.ok && fieldsUnenrichedSuccessfully) {
      toast.success("Alert enriched successfully");
      await mutate();
      handleClose();
    } else {
      toast.error("Failed to enrich alert");
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
    <Transition appear show={isOpen} as={Fragment}>
      <Dialog onClose={handleClose}>
        <Transition.Child
          as={Fragment}
          enter="ease-out duration-300"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-200"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-black/30 z-20" aria-hidden="true" />
        </Transition.Child>
        <Transition.Child
          as={Fragment}
          enter="transition ease-in-out duration-300 transform"
          enterFrom="translate-x-full"
          enterTo="translate-x-0"
          leave="transition ease-in-out duration-300 transform"
          leaveFrom="translate-x-0"
          leaveTo="translate-x-full"
        >
          <Dialog.Panel className="fixed right-0 inset-y-0 w-1/3 bg-white z-30 flex flex-col">
            <div className="flex justify-between items-center min-w-full p-6">
              <h2 className="text-lg font-semibold">Enrich Alert</h2>
            </div>

            <div className="flex-1 overflow-auto pb-6 px-6 mt-2">
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
          </Dialog.Panel>
        </Transition.Child>
      </Dialog>
    </Transition>
  );
};

export default EnrichAlertModal;
