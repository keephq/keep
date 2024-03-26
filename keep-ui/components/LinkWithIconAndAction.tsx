"use client";

import { AnchorHTMLAttributes, ReactNode } from "react";
import Link, { LinkProps } from "next/link";
import { IconType } from "react-icons/lib";
import { Icon } from "@tremor/react";
import { usePathname } from "next/navigation";
import classNames from "classnames";

type LinkWithIconAndActionProps = {
  children: ReactNode;
  icon: IconType;
  actionIcon: IconType;
  actionOnClick: () => void;
} & LinkProps &
  AnchorHTMLAttributes<HTMLAnchorElement>;

export const LinkWithIconAndAction = ({
  icon,
  children,
  actionIcon,
  actionOnClick,
  tabIndex = 0,
  className,
  ...restOfLinkProps
}: LinkWithIconAndActionProps) => {
  const pathname = usePathname();

  const isActive =
    decodeURIComponent(pathname?.toLowerCase() || "") === restOfLinkProps.href;

  return (
    <span
      className={classNames(
        "flex items-center space-x-2 text-sm p-1 text-slate-400 hover:bg-gray-200 font-medium rounded-lg hover:text-orange-500 focus:ring focus:ring-orange-300 group",
        { "bg-gray-200": isActive }
      )}
    >
      <Link
        className={classNames(className, "flex items-center flex-1")}
        tabIndex={tabIndex}
        {...restOfLinkProps}
      >
        <Icon
          className={classNames("group-hover:text-orange-500", {
            "text-orange-500": isActive,
            "text-slate-400": !isActive,
          })}
          icon={icon}
        />
        <span className={classNames({ "text-orange-500": isActive })}>
          {children}
        </span>
      </Link>
      <button onClick={actionOnClick}>
        <Icon className="text-slate-400" icon={actionIcon} />
      </button>
    </span>
  );
};
