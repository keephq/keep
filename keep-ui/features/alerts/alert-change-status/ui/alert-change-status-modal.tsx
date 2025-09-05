import { Button, Title, Subtitle, Switch } from "@tremor/react";
import Modal from "@/components/ui/Modal";
import { useState, useEffect } from "react";
import { AlertDto, Status } from "@/entities/alerts/model";
import { toast } from "react-toastify";
import {
  CheckCircleIcon,
  ExclamationCircleIcon,
  PauseIcon,
  XCircleIcon,
  QuestionMarkCircleIcon,
} from "@heroicons/react/24/outline";
import { useAlerts } from "@/entities/alerts/model/useAlerts";
import { useApi } from "@/shared/lib/hooks/useApi";
import { Select, showErrorToast, Tooltip } from "@/shared/ui";

import { useRevalidateMultiple } from "@/shared/lib/state-utils";

const statusIcons = {
  [Status.Firing]: <ExclamationCircleIcon className="w-4 h-4 mr-2" />,
  [Status.Resolved]: <CheckCircleIcon className="w-4 h-4 mr-2" />,
  [Status.Acknowledged]: <PauseIcon className="w-4 h-4 mr-2" />,
  [Status.Suppressed]: <XCircleIcon className="w-4 h-4 mr-2" />,
  [Status.Pending]: <QuestionMarkCircleIcon className="w-4 h-4 mr-2" />,
};

interface Props {
  alert: AlertDto | AlertDto[] | null | undefined;
  handleClose: () => void;
  presetName: string;
}

export function AlertChangeStatusModal({
  alert,
  handleClose,
  presetName,
}: Props) {
  const api = useApi();
  const [disposeOnNewAlert, setDisposeOnNewAlert] = useState(true);
  const [selectedStatus, setSelectedStatus] = useState<Status | null>(null);
  const revalidateMultiple = useRevalidateMultiple();
  const { alertsMutator } = useAlerts();
  const presetsMutator = () => revalidateMultiple(["/preset"]);

  useEffect(() => {
    setDisposeOnNewAlert(alert && !Array.isArray(alert) ? true : false);
  }, [alert]);

  if (!alert) return null;

  const statusOptions = Object.values(Status)
    .filter((status) => {
      if (!Array.isArray(alert)) {
        return status !== alert.status; // Exclude current status for single alert
      }
      return true; // For batch, show all statuses
    })
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
    if (Array.isArray(alert)) {
      showErrorToast(new Error("Batch status change should use batch handler."));
      return;
    }
    try {
      await api.post(
        `/alerts/enrich?dispose_on_new_alert=${disposeOnNewAlert}`,
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

    const handleChangeStatusBatch = async () => {
    let fingerprints = new Set<string>();
    if (Array.isArray(alert)) {
      alert.forEach((a) => fingerprints.add(a.fingerprint));
    }
    try {
      await api.post(
        `/alerts/batch_enrich?dispose_on_new_alert=${disposeOnNewAlert}`,
        {
          enrichments: {
            status: selectedStatus,
            ...(selectedStatus !== Status.Suppressed && {
              dismissed: false,
              dismissUntil: "",
            }),
          },
          fingerprints: Array.from(fingerprints),
        }
      );

      toast.success("Alert(s) status changed successfully!");
      clearAndClose();
      await alertsMutator();
      await presetsMutator();
    } catch (error) {
      showErrorToast(error, "Failed to change alert(s) status.");
    }
  };

  if (!Array.isArray(alert)) {
    return (
      <Modal onClose={handleClose} isOpen={!!alert}>
        <Title>Change Alert Status</Title>
        <div className="flex mt-2.5">
          <Subtitle>
            Change status from <strong>{alert.status}</strong> to:
        </Subtitle>
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
      <div className="flex justify-between mt-2.5">
        <div>
          <Subtitle>Dispose on new alert</Subtitle>
          <span className="text-xs text-gray-500">
            This will dispose the status when an alert with the same fingerprint
            comes in.
          </span>
        </div>
        <Switch
          checked={disposeOnNewAlert}
          onChange={(checked) => setDisposeOnNewAlert(checked)}
        />
      </div>
      <div className="flex justify-end mt-4 gap-2">
        <Button onClick={handleClose} color="orange" variant="secondary">
          Cancel
        </Button>
        <Button onClick={handleChangeStatus} color="orange">
          Change Status
        </Button>
      </div>
    </Modal>
  );
  }else {
    return (
      <Modal onClose={handleClose} isOpen={!!alert}>
        <Title>Change Alerts Status</Title>
        <div className="flex mt-2.5">
          <Subtitle>
            Change status of {alert.length} alerts to:
          </Subtitle>
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
        <div className="flex justify-between mt-2.5">
          <div>
            <Subtitle>Dispose on new alerts</Subtitle>
            <span className="text-xs text-gray-500">
              This will dispose the status when an alert with the same fingerprint
              comes in.
            </span>
          </div>
          <Switch
            checked={disposeOnNewAlert}
            onChange={(checked) => setDisposeOnNewAlert(checked)}
          />
        </div>
        <div className="flex justify-end mt-4 gap-2">
          <Button onClick={handleClose} color="blue" variant="secondary">
            Cancel
          </Button>
          <Button onClick={handleChangeStatusBatch} color="blue">
            Change Status
          </Button>
        </div>
      </Modal>
    )

  }
}
