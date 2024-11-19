import { AlertDto } from "./models";
import Modal from "@/components/ui/Modal";
import { Button, TextInput } from "@tremor/react";
import { useSession } from "next-auth/react";
import { useApiUrl } from "utils/hooks/useConfig";
import React from "react";

interface EnrichAlertModalProps {
  alert: AlertDto | null | undefined;
  handleClose: () => void;
  mutate: () => void;
}

const EnrichAlertModal: React.FC<EnrichAlertModalProps> = ({
  alert,
  handleClose,
  mutate,
}) => {
  const isOpen = !!alert;
  const { data: session } = useSession();
  const apiUrl = useApiUrl();

  if (!alert) return null;

  const renderFormFields = () => {
    return Object.entries(alert).map(([key, value]) => (
      <div key={key} className="mb-4">
        <label htmlFor={key} className="mb-1">
          {key}:
        </label>
        <TextInput
          id={key}
          name={key}
          value={String(value || "")}
          disabled
          className="mt-1"
        />
      </div>
    ));
  };

  return (
    <Modal
      onClose={handleClose}
      isOpen={isOpen}
      className="overflow-visible max-w-fit"
    >
      <div className="flex justify-between items-center mb-4 min-w-full">
        <h2 className="text-lg font-semibold">Enrich Alert</h2>
        <div className="flex gap-x-2">
          <Button onClick={handleClose} color="orange" variant="secondary">
            Close
          </Button>
        </div>
      </div>

      <div className="form-container">
        {alert ? renderFormFields() : <p>No data available.</p>}
      </div>
    </Modal>
  );
};

export default EnrichAlertModal;
