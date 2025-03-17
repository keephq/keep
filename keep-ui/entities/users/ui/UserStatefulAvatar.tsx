import UserAvatar from "@/components/navbar/UserAvatar";
import { useUser } from "../model/useUser";
import { Icon } from "@tremor/react";
import { UserCircleIcon } from "@heroicons/react/24/outline";
import clsx from "clsx";

export function UserStatefulAvatar({
  email,
  size = "sm",
  color = "gray",
}: {
  email: string;
  size?: "sm" | "xs";
  color?: string;
}) {
  const user = useUser(email);
  const sizeClass = (function (size: "sm" | "xs") {
    if (size === "sm") return "[&>svg]:w-7 [&>svg]:h-7";
    if (size === "xs") return "[&>svg]:w-5 [&>svg]:h-5";
  })(size);
  if (!user) {
    return (
      <Icon
        icon={UserCircleIcon}
        color={color}
        className={clsx("!p-0", sizeClass)}
      />
    );
  }
  return (
    <UserAvatar
      name={user?.name}
      image={user?.picture}
      size={size}
      email={email}
    />
  );
}
