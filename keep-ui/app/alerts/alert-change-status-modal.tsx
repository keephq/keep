import { Button, Title, Subtitle } from "@tremor/react";
import Modal from "@/components/ui/Modal";
import Select, {
  CSSObjectWithLabel,
  ControlProps,
  OptionProps,
  GroupBase,
} from "react-select";
import { useState } from "react";
import { AlertDto, Status } from "./models";
import { getApiURL } from "utils/apiUrl";
import { useSession } from "next-auth/react";
import { toast } from "react-toastify";
import {
  CheckCircleIcon,
  ExclamationCircleIcon,
  PauseIcon,
  XCircleIcon,
  QuestionMarkCircleIcon,
} from "@heroicons/react/24/outline";
import { usePresets } from "utils/hooks/usePresets";
import { useAlerts } from "utils/hooks/useAlerts";
import { useAlertActions } from "utils/hooks/useAlertActions";

const statusIcons = {
  [Status.Firing]: <ExclamationCircleIcon className="w-4 h-4 mr-2" />,
  [Status.Resolved]: <CheckCircleIcon className="w-4 h-4 mr-2" />,
  [Status.Acknowledged]: <PauseIcon className="w-4 h-4 mr-2" />,
  [Status.Suppressed]: <XCircleIcon className="w-4 h-4 mr-2" />,
  [Status.Pending]: <QuestionMarkCircleIcon className="w-4 h-4 mr-2" />,
};

const customSelectStyles = {
  control: (
    base: CSSObjectWithLabel,
    state: ControlProps<
      { value: Status; label: JSX.Element },
      false,
      GroupBase<{ value: Status; label: JSX.Element }>
    >
  ) => ({
    ...base,
    borderColor: state.isFocused ? "orange" : base.borderColor,
    boxShadow: state.isFocused ? "0 0 0 1px orange" : base.boxShadow,
    "&:hover": {
      borderColor: "orange",
    },
  }),
  option: (
    base: CSSObjectWithLabel,
    {
      isFocused,
    }: OptionProps<
      { value: Status; label: JSX.Element },
      false,
      GroupBase<{ value: Status; label: JSX.Element }>
    >
  ) => ({
    ...base,
    backgroundColor: isFocused ? "rgba(255,165,0,0.1)" : base.backgroundColor,
    "&:hover": {
      backgroundColor: "rgba(255,165,0,0.2)",
    },
  }),
};

interface Props {
  alerts: AlertDto[] | null | undefined;
  handleClose: () => void;
  presetName: string;
}

export default function AlertChangeStatusModal({
  alerts,
  handleClose,
  presetName,
}: Props) {
  const { data: session } = useSession();
  const [selectedStatus, setSelectedStatus] = useState<Status | null>(null);
  const { useAllPresets } = usePresets();
  const { mutate: presetsMutator } = useAllPresets();
  const { useAllAlerts } = useAlerts();
  const { mutate: alertsMutator } = useAllAlerts(presetName, {
    revalidateOnMount: false,
  });
  const { changeAlertStatusRequest } = useAlertActions();

  if (!alerts) return null;

  const statusOptions = Object.values(Status)
    .filter((status) => {
      // Exclude status that exists in all alerts
      return alerts?.filter((a) => {
        return a.status !== status;
      }).length === alerts?.length;
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

  let currentCommonStatus = "mixed";
  const uniqueStatuses = new Set(alerts.map((alert) => alert.status));
  if (uniqueStatuses.size === 1) {
    currentCommonStatus = uniqueStatuses.values().next().value;
  }

  const clearAndClose = () => {
    setSelectedStatus(null);
    handleClose();
  };

  const handleChangeStatus = async () => {
    if (!selectedStatus) {
      toast.error("Please select a new status.");
      return;
    }

    try {
      const responses = [];
      for (const alert of alerts) {
        let currentResponse = await changeAlertStatusRequest(alert, selectedStatus);
        responses.push(currentResponse);
      }
      const areAllOk = responses.every((response) => response.ok);

      let message;
      if (areAllOk) {
        if (alerts.length === 1) {
          message = `Alert status changed successfully!`;
        } else {
          message = `Successfully changed status for ${alerts.length} alerts!`;
        }
        toast.success(message);
        clearAndClose();
        await alertsMutator();
        await presetsMutator();
      } else {
        if (alerts.length === 1) {
          message = `Failed to change alert status.`;
        } else {
          const failCount = responses.filter((response) => !response.ok).length;
          message = `Failed to change status for ${failCount} alerts.`;
        }
        toast.error(message);
      }
    } catch (error) {
      toast.error("An error occurred while changing alert status.");
    }
  };

  return (
    <Modal onClose={handleClose} isOpen={!!alerts}>
      <Title>Change Alert Status</Title>
      <Subtitle className="flex items-center">
        Change status from <strong className="mx-2">{currentCommonStatus}</strong> to:
        <div className="flex-1">
          <Select
            options={statusOptions}
            value={statusOptions.find(
              (option) => option.value === selectedStatus
            )}
            onChange={(option) => setSelectedStatus(option?.value || null)}
            placeholder="Select new status"
            className="ml-2"
            styles={customSelectStyles}
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
