import { Card } from "@tremor/react";
import { RectangleStackIcon } from "@heroicons/react/24/outline";
import clsx from "clsx";

export function EmptyStateCard({
  title,
  icon,
  description,
  className,
  children,
  noCard,
}: {
  icon?: React.ElementType;
  title: string;
  description?: string;
  className?: string;
  children?: React.ReactNode;
  noCard?: boolean;
}) {
  const Icon = icon || RectangleStackIcon;
  const Wrapper = noCard ? "div" : Card;
  return (
    <Wrapper
      className={clsx(
        "sm:mx-auto w-full min-h-[400px] text-center flex flex-col items-center justify-center gap-4",
        className
      )}
    >
      <div className="flex flex-col items-center justify-center max-w-md">
        <Icon
          className="mx-auto size-8 text-tremor-content-strong/80"
          aria-hidden={true}
        />
        <p className="mt-2 text-xl font-semibold text-tremor-content-strong dark:text-dark-tremor-content-strong">
          {title}
        </p>
        {description && (
          <p className="text-md text-gray-700 dark:text-dark-tremor-content">
            {description}
          </p>
        )}
      </div>
      {children}
    </Wrapper>
  );
}
