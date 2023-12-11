import { useState } from "react";
import { AlertDto } from "./models";
import { User } from "app/settings/models";
import { NameInitialsAvatar } from "react-name-initials-avatar";

export default function AlertAssignee({
  alert,
  users,
}: {
  alert: AlertDto;
  users: User[];
}) {
  const [imageError, setImageError] = useState(false);
  return !imageError ? (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      className="h-8 w-8 rounded-full"
      src={
        users.find((u) => u.email === alert.assignee)?.picture ||
        `https://ui-avatars.com/api/?name=${
          users.find((u) => u.email === alert.assignee)?.name
        }&background=random`
      }
      height={24}
      width={24}
      alt={`${alert.assignee} profile picture`}
      onError={() => setImageError(true)}
      title={alert.assignee}
    />
  ) : (
    <NameInitialsAvatar
      name={
        users.find((u) => u.email === alert.assignee)?.name || "Unknown User"
      }
      bgColor="orange"
      borderWidth="1px"
      textColor="white"
      size="32px"
    />
  );
}
