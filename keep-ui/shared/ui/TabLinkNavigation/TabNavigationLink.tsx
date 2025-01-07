import { type ElementType, type ReactNode } from "react";
import Link from "next/link";
import { twMerge } from "tailwind-merge";
import { Badge } from "@tremor/react";
import type { LinkProps as NextLinkProps } from "next/link";

type TabNavigationLinkProps = {
  href: string;
  children: ReactNode;
  className?: string;
  isActive?: boolean;
  icon?: ElementType;
  prefetch?: boolean;
  count?: number;
} & NextLinkProps &
  React.AnchorHTMLAttributes<HTMLAnchorElement>;

export function TabNavigationLink({
  href,
  children,
  className,
  isActive,
  icon: Icon,
  prefetch,
  count,
  ...linkProps
}: TabNavigationLinkProps) {
  return (
    <Link
      href={href}
      prefetch={prefetch}
      className={twMerge(
        // Base styles
        "flex items-center whitespace-nowrap outline-none",
        "ui-focus-visible:ring text-sm",
        "border-b-2 border-transparent",
        "transition duration-100 -mb-px px-2 py-2",
        Icon && "gap-1.5",

        // Default/Hover states
        "hover:border-tremor-content hover:text-tremor-content-emphasis text-tremor-content",
        "ui-not-selected:dark:hover:border-dark-tremor-content-emphasis",
        "ui-not-selected:dark:hover:text-dark-tremor-content-emphasis",
        "ui-not-selected:dark:text-dark-tremor-content",

        // Active state
        isActive && [
          "border-orange-500 dark:border-orange-500",
          "text-orange-500 dark:text-orange-500",
          "pointer-events-none",
        ],

        className
      )}
      role="tab"
      aria-selected={isActive}
      tabIndex={isActive ? 0 : -1}
      {...linkProps}
    >
      {Icon && <Icon className="!size-5 flex-shrink-0" />}
      <span className="truncate">{children}</span>
      {count && (
        <Badge size="xs" color="orange">
          {count}
        </Badge>
      )}
    </Link>
  );
}
