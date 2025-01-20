import Image from "next/image";
import { User } from "next-auth";
import { UserAvatar } from "./UserAvatar";
import KeepPng from "../../../../../../public/keep.png";

export function MessageBotHeader() {
  return (
    <div className="flex items-center gap-2 mb-2">
      <Image className="w-8" src={KeepPng} alt="Keep Logo" />
      <span className="font-semibold">Keep Incidents Resolver</span>
    </div>
  );
}

export function MessageUserHeader({ user }: { user?: User | null }) {
  return (
    <div className="flex items-center gap-2 mb-2">
      <UserAvatar user={user} className="h-6 w-6" />
      <span className="font-semibold">{user?.name || "Anonymous"}</span>
    </div>
  );
}
