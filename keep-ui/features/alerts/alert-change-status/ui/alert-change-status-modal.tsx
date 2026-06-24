"use client";

import { useTranslations } from "next-intl";
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
import dynamic from "next/dynamic";
const ReactQuill = dynamic(() => import("react-quill-new"), { ssr: false,
  loading: () => <div className="p-4 text-gray-500 italic">Loading editor...</div>
 });


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
  const t = useTranslations("alerts.changeStatus");
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
      showErrorToast(new Error(t("selectNewStatus")));
      return;
    }
    if (Array.isArray(alert)) {
      showErrorToast(new Error(t("batchStatusChangeError")));
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

      toast.success(t("statusChangedSuccess"));
      clearAndClose();
      await alertsMutator();
      await presetsMutator();
    } catch (error) {
      showErrorToast(error, t("statusChangeFailed"));
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

      toast.success(t("batchStatusChangedSuccess"));
      clearAndClose();
      await alertsMutator();
      await presetsMutator();
    } catch (error) {
      showErrorToast(error, t("batchStatusChangeFailed"));
    }
  };

  if (!Array.isArray(alert)) {
    return (
      <Modal onClose={handleClose} isOpen={!!alert} className="!max-w-none !w-auto inline-block whitespace-nowrap overflow-visible">
        <Title className="text-lg font-semibold">{t("changeAlertStatus")}</Title>
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
            placeholder={t("selectNewStatusPlaceholder")}
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
            tooltip={disposeOnNewAlert ? t("disposeTooltip") : t("keepTooltip")}
          >
            {disposeOnNewAlert ? t("disposingOnNewAlerts") : t("keepingOnNewAlerts")}
          </Button>
        </div>
        <div className="mt-4">
          <Subtitle >{t("addNote")}</Subtitle>
          <div className="mt-4 border border-gray-200 rounded-lg overflow-hidden">
            <ReactQuill
              value={noteContent}
              onChange={(value: string) => setNoteContent(value)}
              theme="snow"
              placeholder={t("statusChangeNotePlaceholder")}
            />
          </div>
        </div>
        <div className="flex justify-end mt-4 gap-2">
          <Button onClick={handleClose} color="orange" variant="secondary">
            {t("cancel")}
          </Button>
          <Button onClick={handleChangeStatus} color="orange">
            {t("changeStatus")}
          </Button>
        </div>
      </Modal>
    );
  } else {
    return (
      <Modal onClose={handleClose} isOpen={!!alert} className="!max-w-none !w-auto inline-block whitespace-nowrap overflow-visible">
        <Title className="text-lg font-semibold">{t("changeAlertsStatusBatch", { count: Array.isArray(alert) ? alert.length : 1 })}</Title>
        <div className="border-t border-gray-200 my-4" />
        <div className="flex mt-2.5 inline-flex items-center">
          <Subtitle
            className="flex items-center bold"
          >
            {t("newStatus")}
          </Subtitle>
          <Select
            options={statusOptions}
            value={statusOptions.find(
              (option) => option.value === selectedStatus
            )}
            onChange={(option) => setSelectedStatus(option?.value || null)}
            placeholder={t("selectNewStatusPlaceholder")}
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
            tooltip={disposeOnNewAlert ? t("disposeTooltip") : t("keepTooltip")}
          >
            {disposeOnNewAlert ? t("disposingOnNewAlerts") : t("keepingOnNewAlerts")}
          </Button>
        </div>
        <div className="mt-4">
          <Subtitle >{t("addNote")}</Subtitle>
          <div className="mt-4 border border-gray-200 rounded-lg overflow-hidden">
            <ReactQuill
              value={noteContent}
              onChange={(value: string) => setNoteContent(value)}
              theme="snow"
              placeholder={t("statusChangeNotePlaceholder")}
            />
          </div>
        </div>
        <div className="flex justify-end mt-4 gap-2">
          <Button onClick={handleClose} color="blue" variant="secondary">
            {t("cancel")}
          </Button>
          <Button onClick={handleChangeStatusBatch} color="blue">
            {t("changeStatus")}
          </Button>
        </div>
      </Modal>
    )

  }
}
