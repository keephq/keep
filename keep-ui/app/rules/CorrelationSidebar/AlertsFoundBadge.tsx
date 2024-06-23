import { Badge } from "@tremor/react";
import Image from "next/image";
import { AlertDto } from "app/alerts/models";

type AlertsFoundBadgeProps = {
  alertsFound: AlertDto[];
  isLoading: boolean;
};

export const AlertsFoundBadge = ({
  alertsFound,
  isLoading,
}: AlertsFoundBadgeProps) => {
  if (alertsFound.length === 0) {
    return (
      <Badge className="mt-3 w-full" color="gray">
        {isLoading
          ? "Getting your alerts..."
          : "No alerts were found with this condition. Please try something else."}
      </Badge>
    );
  }

  const images = alertsFound.reduce<string[]>(
    (acc, { source }) => [...new Set([...acc, ...source])],
    []
  );

  return (
    <Badge className="mt-3 w-full" color="teal">
      <span className="flex items-center">
        {images.map((source, index) => (
          <Image
            className={`inline-block ${index == 0 ? "" : "-ml-2"}`}
            key={source}
            alt={source}
            height={24}
            width={24}
            title={source}
            src={`/icons/${source}-icon.png`}
          />
        ))}
        <span className="ml-4">
          {alertsFound.length} alert(s) were found matching this condition
        </span>
      </span>
    </Badge>
  );
};
