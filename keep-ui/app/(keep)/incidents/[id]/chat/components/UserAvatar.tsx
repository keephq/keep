import Image from "next/image";
import { User } from "next-auth";

interface UserAvatarProps {
  user?: User | null;
  className?: string;
}

export function UserAvatar({ user, className = "" }: UserAvatarProps) {
  if (!user?.image) {
    return (
      <div
        className={`${className} bg-gray-200 rounded-full flex items-center justify-center`}
      >
        <span className="text-gray-500 text-sm">{user?.name?.[0] || "A"}</span>
      </div>
    );
  }

  return (
    <div className={`${className} relative rounded-full overflow-hidden`}>
      <Image
        src={user.image}
        alt={user.name || "User"}
        className="object-cover"
        fill
        sizes="(max-width: 32px) 32px"
      />
    </div>
  );
}
