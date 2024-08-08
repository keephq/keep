import {
  ChevronDoubleRightIcon,
  UserPlusIcon,
} from "@heroicons/react/24/outline";
import { PlusIcon } from "@radix-ui/react-icons";
import { Button } from "@tremor/react";
import { useSession } from "next-auth/react";
import { useState } from "react";
import { IoNotificationsOffOutline } from "react-icons/io5";
import { toast } from "react-toastify";
import { useAlerts } from "utils/hooks/useAlerts";
import AlertAssociateIncidentModal from "./alert-associate-incident-modal";
import { AlertDto } from "./models";
import { useAlertActions } from "utils/hooks/useAlertActions";

interface Props {
  selectedRowIds: string[];
  alerts: AlertDto[];
  presetName: string;
  clearRowSelection: () => void;
  setDismissModalAlert?: (alert: AlertDto[] | null) => void;
  setChangeStatusAlert?: (alerts: AlertDto[] | null) => void;
}

export default function AlertActions({
  selectedRowIds,
  alerts,
  presetName,
  clearRowSelection,
  setDismissModalAlert,
  setChangeStatusAlert
}: Props) {
  const { usePresetAlerts } = useAlerts();
  const { selfAssignAlertRequest } = useAlertActions();
  const { mutate: presetAlertsMutator } = usePresetAlerts(presetName, { revalidateOnMount: false });
  const [isIncidentSelectorOpen, setIsIncidentSelectorOpen] = useState<boolean>(false);
  const { data: session } = useSession();

  const selectedAlerts = alerts.filter((_alert, index) =>
    selectedRowIds.includes(index.toString())
  );
  const notAssignedToMeSelectedAlerts = selectedAlerts.filter((alert) => {
    return session?.user?.email && alert.assignee !== session?.user?.email;
  });

  const selfAssignAlerts = async () => {
    if (
      confirm(
        `After assigning this alerts (${notAssignedToMeSelectedAlerts.length}) to yourself, you won't be able to unassign it until someone else assigns it to himself. Are you sure you want to continue?`
      )
    ) {
      const responses = [];
      for (const alert of notAssignedToMeSelectedAlerts) {
        responses.push(await selfAssignAlertRequest(alert));
      }
      const areAllOk = responses.every((res) => res.ok);
      if (areAllOk) {
        toast.success(`Alerts (${notAssignedToMeSelectedAlerts.length}) assigned to you!`);
        await presetAlertsMutator();
      } else {
        const failedAlerts = responses.filter((res) => !res.ok).length;
        toast.success(`Failed to assign ${failedAlerts} alerts`);
      }
    }
  }

  const showIncidentSelector = () => {
    setIsIncidentSelectorOpen(true);
  }
  const hideIncidentSelector = () => {
    setIsIncidentSelectorOpen(false);
  }

  const handleSuccessfulAlertsAssociation = () => {
    hideIncidentSelector();
    clearRowSelection();
  }

  return (
    <div className="w-full flex justify-end items-center mt-6">
      <Button
        icon={IoNotificationsOffOutline}
        size="sm"
        color="red"
        tooltip="Dismiss selected alerts"
        onClick={() => {
          setDismissModalAlert?.(selectedAlerts);
          clearRowSelection();
        }}
      >
        Dismiss ({selectedRowIds.length})
      </Button>
      <Button
        icon={ChevronDoubleRightIcon}
        size="sm"
        color="orange"
        className="ml-2.5"
        tooltip="Change status of selected alerts"
        onClick={() => {
          setChangeStatusAlert?.(selectedAlerts);
        }}
      >
        Change status ({selectedRowIds.length})
      </Button>
      <Button
        icon={UserPlusIcon}
        size="sm"
        color="orange"
        className="ml-2.5"
        tooltip="Self-assign selected alerts"
        onClick={selfAssignAlerts}
        disabled={notAssignedToMeSelectedAlerts.length === 0}
      >
        Self-assign ({notAssignedToMeSelectedAlerts.length})
      </Button>
      <Button
        icon={PlusIcon}
        size="sm"
        color="orange"
        className="ml-2.5"
        onClick={showIncidentSelector}
        tooltip="Associate events with incident"
      >
        Associate with incident ({selectedRowIds.length})
      </Button>
      <AlertAssociateIncidentModal
          isOpen={isIncidentSelectorOpen}
          alerts={selectedAlerts}
          handleSuccess={handleSuccessfulAlertsAssociation}
          handleClose={hideIncidentSelector}/>
    </div>
  );
}
