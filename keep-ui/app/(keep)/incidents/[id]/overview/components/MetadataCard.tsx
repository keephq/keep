import { Badge } from "@tremor/react";
import { useRouter } from "next/navigation";
import { IncidentDto } from "@/entities/incidents/model";
import { DynamicImageProviderIcon } from "@/components/ui";
import { Link } from "@/components/ui";
import { StatusIcon } from "@/entities/incidents/ui/statuses";
import { getIncidentName } from "@/entities/incidents/lib/utils";

interface MetadataCardProps {
  incident: IncidentDto;
}

export function MetadataCard({ incident }: MetadataCardProps) {
  const router = useRouter();
  const notNullServices = incident.services.filter(
    (service) => service !== "null"
  );

  const filterBy = (key: string, value: string) => {
    router.push(
      `/alerts/feed?cel=${key}%3D%3D${encodeURIComponent(`"${value}"`)}`
    );
  };

  const sections = [
    {
      title: "INVOLVED SERVICES",
      data: notNullServices || [],
      render: (service: string) => (
        <Badge
          key={service}
          color="orange"
          size="sm"
          className="cursor-pointer"
          onClick={() => filterBy("service", service)}
        >
          {service}
        </Badge>
      ),
    },
    {
      title: "ALERT SOURCES",
      data: incident.alert_sources || [],
      render: (source: string) => (
        <Badge
          key={source}
          color="orange"
          size="sm"
          icon={(props: any) => (
            <DynamicImageProviderIcon
              providerType={source.toLowerCase()}
              height="24"
              width="24"
              {...props}
            />
          )}
          className="cursor-pointer"
          onClick={() => filterBy("source", source)}
        >
          {source}
        </Badge>
      ),
    },
    {
      title: "LINKED INCIDENTS",
      data: incident.following_incidents_ids || [],
      render: (incidentId: string) => (
        <Link
          key={incidentId}
          icon={() => <StatusIcon className="!p-0" status={incident.status} />}
          href={`/incidents/${incidentId}`}
        >
          {getIncidentName(incident)}
        </Link>
      ),
    },
    {
      title: "SAME INCIDENT IN THE PAST",
      data: incident.same_incident_in_the_past_id
        ? [incident.same_incident_in_the_past_id]
        : [],
      render: (incidentId: string) => (
        <Link
          key={incidentId}
          icon={() => <StatusIcon className="!p-0" status={incident.status} />}
          href={`/incidents/${incidentId}`}
        >
          {getIncidentName(incident)}
        </Link>
      ),
    },
  ];

  return (
    <div className="rounded-lg space-y-6">
      {sections.map((section) => (
        <div key={section.title} className="space-y-2">
          <h3 className="text-sm text-gray-500">{section.title}</h3>
          {section.data.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {section.data.map((item) => section.render(item))}
            </div>
          ) : (
            <p className="text-sm text-gray-400">
              No {section.title.toLowerCase()} found
            </p>
          )}
        </div>
      ))}
    </div>
  );
}
