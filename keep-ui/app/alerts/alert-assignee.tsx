import { useState } from "react";
import { NameInitialsAvatar } from "react-name-initials-avatar";
import { useUsers } from "utils/hooks/useUsers";

interface Props {
  assignee: string | undefined;
}

export default function AlertAssignee({ assignee }: Props) {
  const [imageError, setImageError] = useState(false);
  const { data: users = [] } = useUsers();

  if (!assignee || users.length < 1) {
    return null;
  }

  const user = users.find((user) => user.email === assignee);
  const userName = user?.name || "Keep";

  return !imageError ? (
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
  );
}
