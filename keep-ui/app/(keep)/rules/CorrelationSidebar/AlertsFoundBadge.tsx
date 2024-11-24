import { Badge } from "@tremor/react";
import Image from "next/image";
import { AlertDto } from "@/app/(keep)/alerts/models";

type AlertsFoundBadgeProps = {
  alertsFound: AlertDto[];
  isLoading: boolean;
  vertical?: boolean;
};

export const AlertsFoundBadge = ({
  alertsFound,
  isLoading,
  vertical = false,
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
      <span
        className={`flex items-center justify-center flex-wrap ${
          vertical ? "mt-2 mb-2 gap-y-3 gap-x-2" : ""
        }`}
      >
        {images.map((source, index) => (
          <Image
            className={`inline-block ${index == 0 || vertical ? "" : "-ml-2"}`}
            key={source}
            alt={source}
            height={24}
            width={24}
            title={source}
            src={`/icons/${source}-icon.png`}
          />
        ))}
        {vertical && <span className="basis-full"></span>}
        <span className="ml-4">
          {alertsFound.length} alert{alertsFound.length > 1 ? "s" : ""} were
          found{vertical && <br />}matching this condition
        </span>
      </span>
    </Badge>
  );
};
