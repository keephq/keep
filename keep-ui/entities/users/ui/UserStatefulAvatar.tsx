import UserAvatar from "@/components/navbar/UserAvatar";
import { useUser } from "../model/useUser";
import { Icon } from "@tremor/react";
import { UserCircleIcon } from "@heroicons/react/24/outline";
import clsx from "clsx";

export function UserStatefulAvatar({
  email,
  size = "sm",
}: {
  email: string;
  size?: "sm" | "xs";
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
        className={clsx("text-gray-600 !p-0", sizeClass)}
      />
    );
  }
  return <UserAvatar name={user?.name} image={user?.picture} size={size} />;
}
