import type { ReactNode } from "react";
import { twMerge } from "tailwind-merge";

interface TabLinkNavigationProps {
  children: ReactNode;
  className?: string;
}

// Purpose of this component is to mimic the tab navigation from Tremor, but with links instead of buttons.
export function TabLinkNavigation({
  children,
  className,
}: TabLinkNavigationProps) {
  return (
    // using overflow-x-auto to allow horizontal scrolling on small screens
    <div className="overflow-x-auto overflow-y-hidden">
      <nav
        className={twMerge(
          "justify-start flex border-b space-x-4",
          "border-tremor-border dark:border-dark-tremor-border",
          "sticky xl:-top-10 -top-4 bg-tremor-background-muted z-10",
          className
        )}
        role="tablist"
        aria-orientation="horizontal"
      >
        {children}
      </nav>
    </div>
  );
}

// Example usage with icons:
{
  /* 
import { BellIcon, ActivityIcon, ClockIcon, NetworkIcon, WorkflowIcon, ChatIcon } from 'lucide-react'

<TabLinkNavigation>
  <TabLinkNavigationLink 
    href="/incident/123"
    isActive={pathname === '/incident/123'}
    icon={BellIcon}
  >
    Overview and Alerts
  </TabLinkNavigationLink>
  <TabLinkNavigationLink
    href="/incident/123/activity"
    isActive={pathname === "/incident/123/activity"}
    icon={ActivityIcon}
  >
    Activity
  </TabLinkNavigationLink>
</TabLinkNavigation>
*/
}
