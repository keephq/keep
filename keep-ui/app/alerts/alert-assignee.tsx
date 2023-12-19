import { useState } from "react";
import { User } from "app/settings/models";
import { NameInitialsAvatar } from "react-name-initials-avatar";

export default function AlertAssignee({
  assignee,
  users,
}: {
  assignee: string | undefined;
  users: User[];
}) {
  const [imageError, setImageError] = useState(false);

  if (!assignee || users.length < 1) {
    return null;
  }

  const user = users.find((user) => user.email === assignee);

  return !imageError ? (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      className="h-8 w-8 rounded-full"
      src={
        user?.picture ||
        `https://ui-avatars.com/api/?name=${user?.name}&background=random`
      }
      height={24}
      width={24}
      alt={`${assignee} profile picture`}
      onError={() => setImageError(true)}
      title={assignee}
    />
  ) : (
    <NameInitialsAvatar
      name={user?.name || "Unknown User"}
      bgColor="orange"
      borderWidth="1px"
      textColor="white"
      size="32px"
    />
  );
}
