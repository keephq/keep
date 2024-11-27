import { AlertDto } from "./models"; // Adjust the import path as needed
import Modal from "@/components/ui/Modal"; // Ensure this path matches your project structure
import { Button, Icon, Switch, Text } from "@tremor/react";
import { toast } from "react-toastify";
import { XMarkIcon } from "@heroicons/react/24/outline";
import "./ViewAlertModal.css";
import React, { useState } from "react";
import { useApi } from "@/shared/lib/hooks/useApi";
import { showErrorToast } from "@/shared/ui/utils/showErrorToast";

interface ViewAlertModalProps {
  alert: AlertDto | null | undefined;
  handleClose: () => void;
  mutate: () => void;
}

const objectToJSONLine = (obj: any) => {
  return JSON.stringify(obj, null, 2).slice(2, -2);
};

export const ViewAlertModal: React.FC<ViewAlertModalProps> = ({
  alert,
  handleClose,
  mutate,
}) => {
  const isOpen = !!alert;
  const [showHighlightedOnly, setShowHighlightedOnly] = useState(false);
  const api = useApi();

  const unEnrichAlert = async (key: string) => {
    if (confirm(`Are you sure you want to un-enrich ${key}?`)) {
      try {
        const requestData = {
          enrichments: [key],
          fingerprint: alert!.fingerprint,
        };
        const response = await api.post(`/alerts/unenrich`, requestData);

        toast.success(`${key} un-enriched successfully!`);
      } catch (error) {
        showErrorToast(error, `Failed to unenrich ${key}`);
      } finally {
        await mutate();
      }
    }
  };

  const highlightKeys = (json: any, keys: string[]) => {
    const lines = Object.keys(json).length;
    const isLast = (index: number) => index == lines - 1;

    return Object.keys(json).map((key: string, index: number) => {
      if (keys.includes(key)) {
        return (
          <p
            key={key}
            className="text-green-600 cursor-pointer line-container"
            onClick={() => unEnrichAlert(key)}
          >
            <span className="un-enrich-icon">
              <Icon
                icon={XMarkIcon}
                tooltip={`Click to un-enrich ${key}`}
                size="xs"
                color="red"
                className="cursor-pointer px-0 py-0"
                variant="outlined"
              />
            </span>
            {objectToJSONLine({ [key]: json[key] })}
            {isLast(index) ? null : ","}
          </p>
        );
      } else {
        if (!showHighlightedOnly || keys.length == 0) {
          return (
            <p key={key}>
              {objectToJSONLine({ [key]: json[key] })}
              {isLast(index) ? null : ","}
            </p>
          );
        }
      }
    });
  };

  const handleCopy = async () => {
    if (alert) {
      try {
        await navigator.clipboard.writeText(JSON.stringify(alert, null, 2));
        toast.success("Alert copied to clipboard!");
      } catch (err) {
        showErrorToast(err, "Failed to copy alert.");
      }
    }
  };

  return (
    <Modal
      onClose={handleClose}
      isOpen={isOpen}
      className="overflow-visible max-w-fit"
    >
      <div className="flex justify-between items-center mb-4 min-w-full">
        <h2 className="text-lg font-semibold">Alert Details</h2>
        <div className="flex gap-x-2">
          {" "}
          {/* Adjust gap as needed */}
          <div className="placeholder-resizing min-w-48"></div>
          <div className="flex items-center space-x-2">
            <Switch
              color="orange"
              id="showHighlightedOnly"
              checked={showHighlightedOnly}
              onChange={() => setShowHighlightedOnly(!showHighlightedOnly)}
            />
            <label
              htmlFor="showHighlightedOnly"
              className="text-sm text-gray-500"
            >
              <Text>Enriched Fields Only</Text>
            </label>
          </div>
          <Button onClick={handleCopy} color="orange">
            Copy to Clipboard
          </Button>
          <Button onClick={handleClose} color="orange" variant="secondary">
            Close
          </Button>
        </div>
      </div>
      {alert && (
        <pre className="p-2 bg-gray-100 rounded mt-2 overflow-auto">
          <p>&#123;</p>
          {highlightKeys(alert, alert.enriched_fields)}
          <p>&#125;</p>
        </pre>
      )}
    </Modal>
  );
};
