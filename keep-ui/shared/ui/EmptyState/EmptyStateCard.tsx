import { Card } from "@tremor/react";
import { CircleStackIcon } from "@heroicons/react/24/outline";
import clsx from "clsx";

export function EmptyStateCard({
  title,
  icon,
  description,
  className,
  children,
}: {
  icon?: React.ElementType;
  title: string;
  description: string;
  className?: string;
  children?: React.ReactNode;
}) {
  const Icon = icon || CircleStackIcon;
  return (
    <Card className={clsx("sm:mx-auto w-full max-w-5xl", className)}>
      <div className="text-center">
        <Icon
          className="mx-auto h-7 w-7 text-tremor-content-subtle dark:text-dark-tremor-content-subtle"
          aria-hidden={true}
        />
        <p className="mt-2 text-tremor-default font-medium text-tremor-content-strong dark:text-dark-tremor-content-strong">
          {title}
        </p>
        <p className="text-tremor-default text-tremor-content dark:text-dark-tremor-content">
          {description}
        </p>
        {children}
      </div>
    </Card>
  );
}
