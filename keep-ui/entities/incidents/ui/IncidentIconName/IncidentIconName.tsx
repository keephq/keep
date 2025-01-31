import { clsx } from "clsx";
import { IncidentDto } from "@/entities/incidents/model";
import { STATUS_ICONS } from "@/entities/incidents/ui";
import { getIncidentName } from "@/entities/incidents/lib/utils";

export function IncidentIconName({
  incident,
  inline = false,
}: {
  incident: IncidentDto;
  inline?: boolean;
}) {
  if (!incident) {
    throw new Error("IncidentIconName: Incident is required");
  }
  return (
    <div
      className={clsx(
        "flex items-center",
        !inline &&
          "px-3 py-2 border rounded-tremor-default border-tremor-border"
      )}
    >
      <div className="w-4 h-4 mr-2">{STATUS_ICONS[incident.status]}</div>
      <div className="flex-1">
        <div className="text-pretty">{getIncidentName(incident)}</div>
      </div>
    </div>
  );
}
