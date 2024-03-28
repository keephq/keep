"use client";

import { AnchorHTMLAttributes, ReactNode } from "react";
import Link, { LinkProps } from "next/link";
import { IconType } from "react-icons/lib";
import { Icon } from "@tremor/react";
import { usePathname } from "next/navigation";
import classNames from "classnames";

type LinkWithIconProps = {
  children: ReactNode;
  icon: IconType;
} & LinkProps &
  AnchorHTMLAttributes<HTMLAnchorElement>;

export const LinkWithIcon = ({
  icon,
  children,
  tabIndex = 0,
  ...restOfLinkProps
}: LinkWithIconProps) => {
  const pathname = usePathname();

  const isActive =
    decodeURIComponent(pathname?.toLowerCase() || "") === restOfLinkProps.href;

  return (
    <Link
      className={classNames(
        "flex items-center space-x-2 text-sm p-1 text-slate-400 hover:bg-stone-200/50 font-medium rounded-lg hover:text-orange-400 focus:ring focus:ring-orange-300 group",
        { "bg-stone-200/50": isActive }
      )}
      tabIndex={tabIndex}
      {...restOfLinkProps}
    >
      <Icon
        className={classNames("group-hover:text-orange-400", {
          "text-orange-400": isActive,
          "text-slate-400": !isActive,
        })}
        icon={icon}
      />
      <span className={classNames({ "text-orange-400": isActive })}>
        {children}
      </span>
    </Link>
  );
};
