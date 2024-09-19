import { Button, Title, Subtitle } from "@tremor/react";
import Modal from "@/components/ui/Modal";
import Select, {
  CSSObjectWithLabel,
  ControlProps,
  OptionProps,
  GroupBase,
} from "react-select";
import { useState } from "react";
import { IncidentDto, Status } from "./models";
import { getApiURL } from "utils/apiUrl";
import { useSession } from "next-auth/react";
import { toast } from "react-toastify";
import {
  CheckCircleIcon,
  ExclamationCircleIcon,
  PauseIcon,
} from "@heroicons/react/24/outline";

const statusIcons = {
  [Status.Firing]: <ExclamationCircleIcon className="w-4 h-4 mr-2" />,
  [Status.Resolved]: <CheckCircleIcon className="w-4 h-4 mr-2" />,
  [Status.Acknowledged]: <PauseIcon className="w-4 h-4 mr-2" />,
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
  incident: IncidentDto | null | undefined;
  mutate: () => void;
  handleClose: () => void;
}

export default function IncidentChangeStatusModal({
  incident,
  mutate,
  handleClose,
}: Props) {
  const { data: session } = useSession();
  const [selectedStatus, setSelectedStatus] = useState<Status | null>(null);
  const [comment, setComment] = useState<string>("");

  if (!incident) return null;

  const statusOptions = Object.values(Status)
    .filter((status) => status !== incident.status) // Exclude current status
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
      toast.error("Please select a new status.");
      return;
    }

    try {
      const response = await fetch(`${getApiURL()}/incidents/${incident.id}/status`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session?.accessToken}`,
        },
        body: JSON.stringify({
            status: selectedStatus,
            comment: comment,
        }),
      });

      if (response.ok) {
        toast.success("Incident status changed successfully!");
        clearAndClose();
        await mutate();
      } else {
        toast.error("Failed to change incident status.");
      }
    } catch (error) {
      toast.error("An error occurred while changing incident status.");
    }
  };

  return (
    <Modal onClose={handleClose} isOpen={!!incident}>
      <Title>Change Incident Status</Title>
      <Subtitle className="flex items-center">
        Change status from <strong className="mx-2">{incident.status}</strong> to:
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
