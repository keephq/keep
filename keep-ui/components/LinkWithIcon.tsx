import { AnchorHTMLAttributes, ReactNode } from "react";
import Link, { LinkProps } from "next/link";
import { IconType } from "react-icons/lib";
import { Badge, Icon } from "@tremor/react";
import { usePathname } from "next/navigation";
import classNames from "classnames";
// import css
import "./LinkWithIcon.css";

type LinkWithIconProps = {
  children: ReactNode;
  icon: IconType;
  iconOverride?: IconType;  // Added icon override property
  count?: number;
  isBeta?: boolean;
  shouldPulse?: boolean;
} & LinkProps & AnchorHTMLAttributes<HTMLAnchorElement>;

export const LinkWithIcon = ({
  icon,
  iconOverride,  // Included in destructuring
  children,
  tabIndex = 0,
  count,
  isBeta = false,
  shouldPulse = false,
  ...restOfLinkProps
}: LinkWithIconProps) => {
  const pathname = usePathname();
  const isActive = decodeURIComponent(pathname?.toLowerCase() || "") === restOfLinkProps.href;
  const actualIcon = iconOverride || icon;  // Use override if available

  const iconClasses = classNames({
    "group-hover:text-orange-400": true,
    "text-orange-400": isActive,
    "text-slate-400": !isActive,
    "pulse-icon": shouldPulse
  });

  return (
    <Link
      className={classNames(
        "flex items-center justify-between text-sm p-1 text-slate-400 hover:bg-stone-200/50 font-medium rounded-lg hover:text-orange-400 focus:ring focus:ring-orange-300 group w-full",
        { "bg-stone-200/50": isActive }
      )}
      tabIndex={tabIndex}
      {...restOfLinkProps}
    >
      <div className="flex items-center space-x-2">
        <Icon
          className={iconClasses}
          icon={actualIcon}
        />
        <span className={classNames({ "text-orange-400": isActive })}>
          {children}
        </span>
      </div>
      <div className="flex items-center">
        {count !== undefined && count !== null && (
          <Badge
            className="z-10"
            size="xs"
            color="orange"
          >
            {count}
          </Badge>
        )}
        {isBeta && (
          <Badge color="orange" size="xs" className="ml-2">
            Beta
          </Badge>
        )}
      </div>
    </Link>
  );
};
