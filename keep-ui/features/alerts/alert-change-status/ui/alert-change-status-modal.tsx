import { Button, Title, Subtitle, Switch } from "@tremor/react";
import Modal from "@/components/ui/Modal";
import { useState, useEffect } from "react";
import { AlertDto, Status } from "@/entities/alerts/model";
import { toast } from "react-toastify";
import {
  CheckCircleIcon,
  ExclamationCircleIcon,
  PauseIcon,
  CircleStackIcon,
} from "@heroicons/react/24/outline";
import { useAlerts } from "@/entities/alerts/model/useAlerts";
import { useApi } from "@/shared/lib/hooks/useApi";
import { Select, showErrorToast, Tooltip } from "@/shared/ui";

import { useRevalidateMultiple } from "@/shared/lib/state-utils";
import ReactQuill from "react-quill-new";

const statusIcons = {
  [Status.Firing]: <ExclamationCircleIcon className="w-5 h-5 text-red-500 mr-2" />,
  [Status.Resolved]: <CheckCircleIcon className="w-5 h-5 text-green-500 mr-2" />,
  [Status.Acknowledged]: <PauseIcon className="w-5 h-5 text-gray-500 mr-2" />,
  [Status.Suppressed]: <CircleStackIcon className="w-5 h-5 text-gray-500 mr-2" />,
  [Status.Pending]: <CircleStackIcon className="w-5 h-5 text-gray-500 mr-2" />,
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
  const [noteContent, setNoteContent] = useState<string>("");

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
    setNoteContent("");
    setDisposeOnNewAlert(true);
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
            ...(noteContent && noteContent.trim() !== "" && {
              note: noteContent,
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
            ...(noteContent && noteContent.trim() !== "" && {
              note: noteContent,
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
      <Modal onClose={handleClose} isOpen={!!alert} className="!max-w-none !w-auto inline-block whitespace-nowrap overflow-visible">
        <Title className="text-lg font-semibold">Change Alert Status</Title>
        <div className="border-t border-gray-200 my-4" />
        <div className="flex mt-2.5 inline-flex items-center">
          <Subtitle
            className="flex items-center bold"
          >
            New status:
          </Subtitle>
          <Select
            options={statusOptions}
            value={statusOptions.find(
              (option) => option.value === selectedStatus
            )}
            onChange={(option) => setSelectedStatus(option?.value || null)}
            placeholder="Select new status"
            className="ml-2"
            styles={{
              control: (base) => ({
                ...base,
                width: "max-content",
                minWidth: "180px",
              }),
            }}
          />
          <Button
            variant={disposeOnNewAlert ? "primary" : "secondary"}
            className="ml-4"
            size="xs"
            onClick={() => setDisposeOnNewAlert(!disposeOnNewAlert)}
            tooltip={disposeOnNewAlert ? "Dispose the status when a new alert comes in." : "Keep the status when a new alert comes in."}
          >
            {disposeOnNewAlert ? "Disposing on new alerts" : "Keeping on new alerts"}
          </Button>
        </div>
        <div className="mt-4">
          <Subtitle >Add Note</Subtitle>
          <div className="mt-4 border border-gray-200 rounded-lg overflow-hidden">
            <ReactQuill
              value={noteContent}
              onChange={(value: string) => setNoteContent(value)}
              theme="snow"
              placeholder="Add the reason for status change here..."
            />
          </div>
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
  } else {
    return (
      <Modal onClose={handleClose} isOpen={!!alert} className="!max-w-none !w-auto inline-block whitespace-nowrap overflow-visible">
        <Title className="text-lg font-semibold">Change Alerts Status - Alert(s) selected: {Array.isArray(alert) ? alert.length : 1}</Title>
        <div className="border-t border-gray-200 my-4" />
        <div className="flex mt-2.5 inline-flex items-center">
          <Subtitle
            className="flex items-center bold"
          >
            New status:
          </Subtitle>
          <Select
            options={statusOptions}
            value={statusOptions.find(
              (option) => option.value === selectedStatus
            )}
            onChange={(option) => setSelectedStatus(option?.value || null)}
            placeholder="Select new status"
            className="ml-2"
            styles={{
              control: (base) => ({
                ...base,
                width: "max-content",
                minWidth: "180px",
              }),
            }}
          />
          <Button
            variant={disposeOnNewAlert ? "primary" : "secondary"}
            className="ml-4"
            size="xs"
            onClick={() => setDisposeOnNewAlert(!disposeOnNewAlert)}
            tooltip={disposeOnNewAlert ? "Dispose the status when a new alert comes in." : "Keep the status when a new alert comes in."}
          >
            {disposeOnNewAlert ? "Disposing on new alerts" : "Keeping on new alerts"}
          </Button>
        </div>
        <div className="mt-4">
          <Subtitle >Add Note</Subtitle>
          <div className="mt-4 border border-gray-200 rounded-lg overflow-hidden">
            <ReactQuill
              value={noteContent}
              onChange={(value: string) => setNoteContent(value)}
              theme="snow"
              placeholder="Add the reason for status change here..."
            />
          </div>
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
