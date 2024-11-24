import clsx from "clsx";
import Image from "next/image";

interface Props {
  image: string | null | undefined;
  name: string;
  size?: "sm" | "xs";
}

export const getInitials = (name: string) =>
  ((name.match(/(^\S\S?|\b\S)?/g) ?? []).join("").match(/(^\S|\S$)?/g) ?? [])
    .join("")
    .toUpperCase();

export default function UserAvatar({ image, name, size = "sm" }: Props) {
  const sizeClass = (function (size: "sm" | "xs") {
    if (size === "sm") return "w-7 h-7";
    if (size === "xs") return "w-5 h-5";
  })(size);
  const sizeValue = (function (size: "sm" | "xs") {
    if (size === "sm") return 28;
    if (size === "xs") return 20;
  })(size);
  return image ? (
    <Image
      className={clsx("rounded-full inline", sizeClass)}
      src={image}
      alt="user avatar"
      width={sizeValue}
      height={sizeValue}
    />
  ) : (
    <span
      className={clsx(
        "relative inline-flex items-center justify-center overflow-hidden bg-orange-400 rounded-full dark:bg-gray-600",
        sizeClass
      )}
    >
      <span className="font-medium text-white text-xs">
        {getInitials(name)}
      </span>
    </span>
  );
}
