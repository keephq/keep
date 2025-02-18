import { Button, Card } from "@tremor/react";
import { CircleStackIcon } from "@heroicons/react/24/outline";

export function EmptyStateCard({
  title,
  description,
  buttonText,
  onClick,
  className,
}: {
  title: string;
  description?: string;
  buttonText?: string;
  onClick?: (e: React.MouseEvent) => void;
  className?: string;
}) {
  return (
    <Card
      className={`sm:mx-auto w-full max-w-5xl ${className ? className : ""}`}
    >
      <div className="text-center">
        <CircleStackIcon
          className="mx-auto h-7 w-7 text-tremor-content-subtle dark:text-dark-tremor-content-subtle"
          aria-hidden={true}
        />
        <p className="mt-4 text-tremor-default font-medium text-tremor-content-strong dark:text-dark-tremor-content-strong">
          {title}
        </p>
        {description && (
          <p className="text-tremor-default text-tremor-content dark:text-dark-tremor-content">
            {description}
          </p>
        )}
        {buttonText && (
          <Button className="mt-4" color="orange" onClick={onClick}>
            {buttonText}
          </Button>
        )}
      </div>
    </Card>
  );
}
