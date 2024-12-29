import { Button, Title, Subtitle } from "@tremor/react";
import Modal from "@/components/ui/Modal";
import { useState } from "react";
import { AlertDto, Status } from "@/entities/alerts/model";
import { toast } from "react-toastify";
import {
  CheckCircleIcon,
  ExclamationCircleIcon,
  PauseIcon,
  XCircleIcon,
  QuestionMarkCircleIcon,
} from "@heroicons/react/24/outline";
import { useAlerts } from "utils/hooks/useAlerts";
import { useApi } from "@/shared/lib/hooks/useApi";
import { Select, showErrorToast } from "@/shared/ui";

import { useRevalidateMultiple } from "@/shared/lib/state-utils";

const statusIcons = {
  [Status.Firing]: <ExclamationCircleIcon className="w-4 h-4 mr-2" />,
  [Status.Resolved]: <CheckCircleIcon className="w-4 h-4 mr-2" />,
  [Status.Acknowledged]: <PauseIcon className="w-4 h-4 mr-2" />,
  [Status.Suppressed]: <XCircleIcon className="w-4 h-4 mr-2" />,
  [Status.Pending]: <QuestionMarkCircleIcon className="w-4 h-4 mr-2" />,
};

interface Props {
  alert: AlertDto | null | undefined;
  handleClose: () => void;
  presetName: string;
}

export default function AlertChangeStatusModal({
  alert,
  handleClose,
  presetName,
}: Props) {
  const api = useApi();
  const [selectedStatus, setSelectedStatus] = useState<Status | null>(null);
  const revalidateMultiple = useRevalidateMultiple();
  const presetsMutator = () => revalidateMultiple(["/preset"]);
  const { useAllAlerts } = useAlerts();
  const { mutate: alertsMutator } = useAllAlerts(presetName, {
    revalidateOnMount: false,
  });

  if (!alert) return null;

  const statusOptions = Object.values(Status)
    .filter((status) => status !== alert.status) // Exclude current status
    .map((status) => ({
      value: status,
      label: (
        <div className="flex items-center">
          {statusIcons[status]}
          <span>{status.charAt(0).toUpperCase() + status.slice(1)}</span>
        </div>
      ),
    }));

  const clearAndClose = () => {
    setSelectedStatus(null);
    handleClose();
  };

  const handleChangeStatus = async () => {
    if (!selectedStatus) {
      showErrorToast(new Error("Please select a new status."));
      return;
    }

    try {
      const response = await api.post(
        `/alerts/enrich?dispose_on_new_alert=true`,
        {
          enrichments: {
            status: selectedStatus,
            ...(selectedStatus !== Status.Suppressed && {
              dismissed: false,
              dismissUntil: "",
            }),
          },
          fingerprint: alert.fingerprint,
        }
      );

      toast.success("Alert status changed successfully!");
      clearAndClose();
      await alertsMutator();
      await presetsMutator();
    } catch (error) {
      showErrorToast(error, "Failed to change alert status.");
    }
  };

  return (
    <Modal onClose={handleClose} isOpen={!!alert}>
      <Title>Change Alert Status</Title>
      <Subtitle className="flex items-center">
        Change status from <strong className="mx-2">{alert.status}</strong> to:
        <div className="flex-1">
          <Select
            options={statusOptions}
            value={statusOptions.find(
              (option) => option.value === selectedStatus
            )}
            onChange={(option) => setSelectedStatus(option?.value || null)}
            placeholder="Select new status"
            className="ml-2"
          />
        </div>
      </Subtitle>
      <div className="flex justify-end mt-4 space-x-2">
        <Button onClick={handleChangeStatus} color="orange">
          Change Status
        </Button>
        <Button onClick={handleClose} color="orange" variant="secondary">
          Cancel
        </Button>
      </div>
    </Modal>
  );
}
