import { useState } from "react";
import { NameInitialsAvatar } from "react-name-initials-avatar";
import { useUsers } from "utils/hooks/useUsers";
import { callAssignEndpoint } from "./alert-assignment";
import {Button, Icon} from "@tremor/react";
import { useAlerts } from "../../utils/hooks/useAlerts";
import { useSession } from "next-auth/react";
import {AlertDto} from "./models";
import {PencilSquareIcon, XCircleIcon} from "@heroicons/react/24/outline";

interface Props {
  assignee: string | undefined;
  alert: AlertDto;
  presetName: string;
}

export default function AlertAssignee({ assignee, alert, presetName}: Props) {
  const [imageError, setImageError] = useState(false);
  const { data: users = [] } = useUsers();
  const { usePresetAlerts } = useAlerts();
  const { mutate, isLoading: isValidating } = usePresetAlerts(presetName);
  const { data: session } = useSession();

  if (!assignee || users.length < 1) {
    return null;
  }

  const user = users.find((user) => user.email === assignee);
  const userName = user?.name || "Keep";


  return <div className="flex justify-between">
    {!imageError ? (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        className="h-8 w-8 rounded-full"
        src={
          user?.picture ||
          `https://ui-avatars.com/api/?name=${userName}&background=random`
        }
        height={24}
        width={24}
        alt={`${assignee} profile picture`}
        onError={() => setImageError(true)}
        title={assignee}
      />
    ) : (
      <NameInitialsAvatar
        name={userName}
        bgColor="orange"
        borderWidth="1px"
        textColor="white"
        size="32px"
      />
    )}

    <Icon
      icon={XCircleIcon}
      tooltip="Unassign user"
      size="sm"
      color="gray"
      className="cursor-pointer"
      onClick={async (e) => {
        e.stopPropagation();
        e.preventDefault();
        await callAssignEndpoint({
          unassign: true,
          alert,
          session,
          mutate
        });
      }}
    />
  </div>
}
