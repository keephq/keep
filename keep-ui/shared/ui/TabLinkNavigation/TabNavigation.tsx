import { ElementType, type ReactNode } from "react";
import Link from "next/link";
import { twMerge } from "tailwind-merge";

interface TabNavigationProps {
  children: ReactNode;
  className?: string;
}

interface TabNavigationLinkProps {
  href: string;
  children: ReactNode;
  className?: string;
  isActive?: boolean;
  icon?: ElementType;
}

export function TabNavigation({ children, className }: TabNavigationProps) {
  return (
    <nav
      className={twMerge(
        "justify-start overflow-x-clip flex border-b space-x-4",
        "border-tremor-border dark:border-dark-tremor-border",
        "sticky xl:-top-10 -top-4 bg-tremor-background-muted z-10",
        className
      )}
      role="tablist"
      aria-orientation="horizontal"
    >
      {children}
    </nav>
  );
}

export function TabNavigationLink({
  href,
  children,
  className,
  isActive,
  icon: Icon,
}: TabNavigationLinkProps) {
  return (
    <Link
      href={href}
      className={twMerge(
        // Base styles
        "flex items-center whitespace-nowrap truncate max-w-xs outline-none",
        "ui-focus-visible:ring text-sm",
        "border-b-2 border-transparent",
        "transition duration-100 -mb-px px-2 py-2",
        Icon && "gap-2",

        // Default/Hover states
        "hover:border-tremor-content hover:text-tremor-content-emphasis text-tremor-content",
        "ui-not-selected:dark:hover:border-dark-tremor-content-emphasis",
        "ui-not-selected:dark:hover:text-dark-tremor-content-emphasis",
        "ui-not-selected:dark:text-dark-tremor-content",

        // Active state
        isActive && [
          "border-orange-500 dark:border-orange-500",
          "text-orange-500 dark:text-orange-500",
        ],

        className
      )}
      role="tab"
      aria-selected={isActive}
      tabIndex={isActive ? 0 : -1}
    >
      {Icon && <Icon className="size-5" />}
      <span>{children}</span>
    </Link>
  );
}

// Example usage with icons:
{
  /* 
import { BellIcon, ActivityIcon, ClockIcon, NetworkIcon, WorkflowIcon, ChatIcon } from 'lucide-react'

<TabNavigation>
  <TabNavigationLink 
    href="/incident/123"
    isActive={pathname === '/incident/123'}
    icon={BellIcon}
  >
    Overview and Alerts
  </TabNavigationLink>
  <TabNavigationLink
    href="/incident/123/activity"
    isActive={pathname === "/incident/123/activity"}
    icon={ActivityIcon}
  >
    Activity
  </TabNavigationLink>
</TabNavigation>
*/
}
