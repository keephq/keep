"use client";

import { AnchorHTMLAttributes, ReactNode } from "react";
import Link, { LinkProps } from "next/link";
import { IconType } from "react-icons/lib";
import { Badge, Icon } from "@tremor/react";
import { usePathname } from "next/navigation";
import classNames from "classnames";

type LinkWithIconProps = {
  children: ReactNode;
  icon: IconType;
  isBeta?: boolean;
} & LinkProps &
  AnchorHTMLAttributes<HTMLAnchorElement>;

export const LinkWithIcon = ({
  icon,
  children,
  tabIndex = 0,
  isBeta = false,
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
      <div className="flex w-full justify-between items-center">
        <div className="flex items-center">
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
        </div>
        {isBeta && (
          <Badge color="orange" size="xs">
            Beta
          </Badge>
        )}
      </div>
    </Link>
  );
};
