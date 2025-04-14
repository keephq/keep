import clsx from "clsx";
import Image from "next/image";

interface Props {
  image: string | null | undefined;
  name: string;
  size?: "sm" | "xs";
  email?: string;
}

export const getInitials = (name: string) =>
  ((name.match(/(^\S\S?|\b\S)?/g) ?? []).join("").match(/(^\S|\S$)?/g) ?? [])
    .join("")
    .toUpperCase();

const getBackgroundColor = (name: string) => {
  const hash = name.split("").reduce((acc, char) => {
    return acc + char.charCodeAt(0);
  }, 0);
  return `#${hash.toString(16).padStart(6, "0")}`;
};

export default function UserAvatar({ image, name, size = "sm", email }: Props) {
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
      className={clsx("rounded-full inline invert-dark-mode", sizeClass)}
      src={image}
      alt="user avatar"
      width={sizeValue}
      height={sizeValue}
      title={email ?? name}
    />
  ) : (
    <span
      className={clsx(
        "relative inline-flex items-center justify-center overflow-hidden rounded-full dark:bg-gray-600",
        sizeClass
      )}
      style={{ backgroundColor: getBackgroundColor(name) }}
      title={email ?? name}
    >
      <span
        className={clsx(
          "font-medium text-white text-xs",
          size === "xs" ? "text-[0.6rem]" : "text-xs"
        )}
      >
        {getInitials(name)}
      </span>
    </span>
  );
}
