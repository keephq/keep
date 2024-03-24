"use client";

import { AnchorHTMLAttributes, ReactNode } from "react";
import Link, { LinkProps } from "next/link";
import { IconType } from "react-icons/lib";
import { Icon } from "@tremor/react";
import { usePathname } from "next/navigation";
import classNames from "classnames";

type StyledLinkProps = {
  children: ReactNode;
  icon: IconType;
} & LinkProps &
  AnchorHTMLAttributes<HTMLAnchorElement>;

export const LinkWithIcon = ({
  icon,
  children,
  tabIndex = 0,
  ...restOfLinkProps
}: StyledLinkProps) => {
  const pathname = usePathname();

  const isActive =
    decodeURIComponent(pathname?.toLowerCase() || "") === restOfLinkProps.href;

  return (
    <Link
      className={classNames(
        "flex items-center space-x-2 text-sm p-1 text-gray-700 hover:bg-gray-200 font-medium rounded-lg hover:text-orange-500 focus:ring focus:ring-orange-300 group",
        { "bg-gray-200": isActive }
      )}
      tabIndex={tabIndex}
      {...restOfLinkProps}
    >
      <Icon className="text-gray-700 group-hover:text-orange-500" icon={icon} />
      <span>{children}</span>
    </Link>
  );
};
