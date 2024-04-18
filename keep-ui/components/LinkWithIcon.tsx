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
  count?: number;
} & LinkProps &
  AnchorHTMLAttributes<HTMLAnchorElement>;

export const LinkWithIcon = ({
  icon,
  children,
  tabIndex = 0,
  count,
  ...restOfLinkProps
}: LinkWithIconProps) => {
  const pathname = usePathname();

  const isActive =
    decodeURIComponent(pathname?.toLowerCase() || "") === restOfLinkProps.href;

    return (
      <Link
        className={classNames(
          "flex items-center justify-between space-x-2 text-sm p-1 text-slate-400 hover:bg-stone-200/50 font-medium rounded-lg hover:text-orange-400 focus:ring focus:ring-orange-300 group w-full",
          { "bg-stone-200/50": isActive }
        )}
        tabIndex={tabIndex}
        {...restOfLinkProps}
      >
        <div className="flex items-center space-x-2">
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
        {(count !== undefined && count !== null) && (
  <Badge
    className="z-10 mr-2"
    size="xs"
    color="orange"
  >
    {count}
  </Badge>
)}

      </Link>
    );
  };
