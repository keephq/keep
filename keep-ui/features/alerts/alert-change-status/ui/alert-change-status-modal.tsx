import { Button, Subtitle, Title } from "@tremor/react";
import Modal from "@/components/ui/Modal";
import { useState } from "react";
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
import { Select, showErrorToast } from "@/shared/ui";

import { useRevalidateMultiple } from "@/shared/lib/state-utils";
import dynamic from "next/dynamic";
import { useI18n } from "@/i18n/hooks/useI18n";

function LoadingEditor() {
  const { t } = useI18n();

  return (
    <div className="p-4 text-gray-500 italic">
      {t("alerts.changeStatus.loadingEditor")}
    </div>
  );
}

const ReactQuill = dynamic(() => import("react-quill-new"), {
  ssr: false,
  loading: LoadingEditor,
});

const statusIcons = {
  [Status.Firing]: (
    <ExclamationCircleIcon className="w-5 h-5 text-red-500 mr-2" />
  ),
  [Status.Resolved]: (
    <CheckCircleIcon className="w-5 h-5 text-green-500 mr-2" />
  ),
  [Status.Acknowledged]: <PauseIcon className="w-5 h-5 text-gray-500 mr-2" />,
  [Status.Suppressed]: (
    <CircleStackIcon className="w-5 h-5 text-gray-500 mr-2" />
  ),
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
  presetName: _presetName,
}: Props) {
  const { t } = useI18n();
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
          <span>{t(`alerts.status.${status}`)}</span>
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
      showErrorToast(new Error(t("alerts.changeStatus.selectStatusError")));
      return;
    }
    if (Array.isArray(alert)) {
      showErrorToast(new Error(t("alerts.changeStatus.batchHandlerError")));
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
            ...(noteContent &&
              noteContent.trim() !== "" && {
                note: noteContent,
              }),
          },
          fingerprint: alert.fingerprint,
        }
      );

      toast.success(t("alerts.changeStatus.successSingle"));
      clearAndClose();
      await alertsMutator();
      await presetsMutator();
    } catch (error) {
      showErrorToast(error, t("alerts.changeStatus.failedSingle"));
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
            ...(noteContent &&
              noteContent.trim() !== "" && {
                note: noteContent,
              }),
          },
          fingerprints: Array.from(fingerprints),
        }
      );

      toast.success(t("alerts.changeStatus.successMultiple"));
      clearAndClose();
      await alertsMutator();
      await presetsMutator();
    } catch (error) {
      showErrorToast(error, t("alerts.changeStatus.failedMultiple"));
    }
  };

  const modalTitle = Array.isArray(alert)
    ? t("alerts.changeStatus.batchTitle", { count: alert.length })
    : t("alerts.changeStatus.title");

  const handleSubmit = Array.isArray(alert)
    ? handleChangeStatusBatch
    : handleChangeStatus;

  return (
    <Modal
      onClose={handleClose}
      isOpen={!!alert}
      className="!max-w-none !w-auto inline-block whitespace-nowrap overflow-visible"
    >
      <Title className="text-lg font-semibold">{modalTitle}</Title>
      <div className="border-t border-gray-200 my-4" />
      <div className="flex mt-2.5 inline-flex items-center">
        <Subtitle className="flex items-center bold">
          {t("alerts.changeStatus.newStatus")}
        </Subtitle>
        <Select
          options={statusOptions}
          value={statusOptions.find(
            (option) => option.value === selectedStatus
          )}
          onChange={(option) => setSelectedStatus(option?.value || null)}
          placeholder={t("alerts.changeStatus.selectNewStatus")}
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
          tooltip={
            disposeOnNewAlert
              ? t("alerts.changeStatus.disposeTooltip")
              : t("alerts.changeStatus.keepTooltip")
          }
        >
          {disposeOnNewAlert
            ? t("alerts.changeStatus.disposeOnNewAlerts")
            : t("alerts.changeStatus.keepOnNewAlerts")}
        </Button>
      </div>
      <div className="mt-4">
        <Subtitle>{t("alerts.actions.addNote")}</Subtitle>
        <div className="mt-4 border border-gray-200 rounded-lg overflow-hidden">
          <ReactQuill
            value={noteContent}
            onChange={(value: string) => setNoteContent(value)}
            theme="snow"
            placeholder={t("alerts.changeStatus.addNotePlaceholder")}
          />
        </div>
      </div>
      <div className="flex justify-end mt-4 gap-2">
        <Button
          onClick={handleClose}
          color={Array.isArray(alert) ? "blue" : "orange"}
          variant="secondary"
        >
          {t("common.actions.cancel")}
        </Button>
        <Button
          onClick={handleSubmit}
          color={Array.isArray(alert) ? "blue" : "orange"}
        >
          {t("alerts.actions.changeStatus")}
        </Button>
      </div>
    </Modal>
  );
}
