import Image from "next/image";

interface Props {
  image: string | null | undefined;
  name: string;
}

export const getInitials = (name: string) =>
  ((name.match(/(^\S\S?|\b\S)?/g) ?? []).join("").match(/(^\S|\S$)?/g) ?? [])
    .join("")
    .toUpperCase();

export default function UserAvatar({ image, name }: Props) {
  return image ? (
    <Image
      className="rounded-full w-7 h-7 inline"
      src={image}
      alt="user avatar"
      width={28}
      height={28}
    />
  ) : (
    <span className="relative inline-flex items-center justify-center w-7 h-7 overflow-hidden bg-orange-400 rounded-full dark:bg-gray-600">
      <span className="font-medium text-white text-xs">
        {getInitials(name)}
      </span>
    </span>
  );
}
