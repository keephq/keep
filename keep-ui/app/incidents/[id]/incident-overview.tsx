"use client";

import type { IncidentDto } from "@/entities/incidents/model";
import React from "react";
import { useIncident } from "@/utils/hooks/useIncidents";
import { format } from "date-fns";
import { Disclosure } from "@headlessui/react";
import classNames from "classnames";
import { IoChevronDown } from "react-icons/io5";
import remarkRehype from "remark-rehype";
import rehypeRaw from "rehype-raw";
import Markdown from "react-markdown";
import { Badge, Callout } from "@tremor/react";
import { Link } from "@/components/ui";
import { IncidentChangeStatusSelect } from "@/features/change-incident-status";
import { getIncidentName } from "@/entities/incidents/lib/utils";
import TimeAgo from "react-timeago";

interface Props {
  incident: IncidentDto;
}

const FieldHeader = ({ children }: { children: React.ReactNode }) => (
  <h3 className="text-sm text-gray-500 font-semibold">{children}</h3>
);

function Summary({
  title,
  summary,
  collapsable,
  className,
}: {
  title: string;
  summary: string;
  collapsable?: boolean;
  className?: string;
}) {
  const formatedSummary = (
    <Markdown remarkPlugins={[remarkRehype]} rehypePlugins={[rehypeRaw]}>
      {summary}
    </Markdown>
  );

  if (collapsable) {
    return (
      <Disclosure as="div" className={classNames("space-y-1", className)}>
        <Disclosure.Button>
          {({ open }) => (
            <h4 className="text-gray-500 text-sm inline-flex justify-between items-center gap-1">
              <span>{title}</span>
              <IoChevronDown
                className={classNames({ "rotate-180": open }, "text-slate-400")}
              />
            </h4>
          )}
        </Disclosure.Button>

        <Disclosure.Panel as="div" className="space-y-2 relative">
          {formatedSummary}
        </Disclosure.Panel>
      </Disclosure>
    );
  }

  return (
    <div className={className}>
      <FieldHeader>{title}</FieldHeader>
      {/*TODO: suggest generate summary if it's empty*/}
      {summary ? <div>{formatedSummary}</div> : <p>No summary yet</p>}
    </div>
  );
}

function MergedCallout({
  merged_into_incident_id,
}: {
  merged_into_incident_id: string;
}) {
  const { data: merged_incident } = useIncident(merged_into_incident_id);

  if (!merged_incident) {
    return null;
  }

  return (
    <Callout title="This incident was merged" color="purple" className="mb-2">
      <p>
        This incident was merged into{" "}
        <Link href={`/incidents/${merged_incident?.id}`}>
          {getIncidentName(merged_incident)}
        </Link>
      </p>
    </Callout>
  );
}

export function IncidentOverview({ incident: initialIncidentData }: Props) {
  const { data: fetchedIncident } = useIncident(initialIncidentData.id, {
    fallbackData: initialIncidentData,
    revalidateOnMount: false,
  });
  const incident = fetchedIncident || initialIncidentData;
  const formatString = "dd MMM yy, HH:mm.ss 'UTC'";
  const summary = incident.user_summary || incident.generated_summary;
  // Why do we have "null" in services?
  const notNullServices = incident.services.filter(
    (service) => service !== "null"
  );

  return (
    <div className="flex gap-6 w-full">
      <div className="basis-2/3 grow">
        <div className="max-w-3xl flex flex-col gap-2">
          {incident.merged_into_incident_id && (
            <MergedCallout
              merged_into_incident_id={incident.merged_into_incident_id}
            />
          )}
          <Summary title="Summary" summary={summary} />
          {incident.user_summary && incident.generated_summary ? (
            <Summary
              title="AI version"
              summary={incident.generated_summary}
              collapsable={true}
            />
          ) : null}
          <div className="flex flex-col gap-2">
            <FieldHeader>Involved services</FieldHeader>
            <div className="flex flex-wrap gap-1">
              {notNullServices.length > 0
                ? notNullServices.map((service) => (
                    <Badge key={service} size="sm">
                      {service}
                    </Badge>
                  ))
                : "No services involved"}
            </div>
          </div>
        </div>
      </div>
      <div className="shrink min-w-64 flex flex-col gap-2">
        <div>
          <FieldHeader>Status</FieldHeader>
          <IncidentChangeStatusSelect
            incidentId={incident.id}
            value={incident.status}
          />
        </div>
        <div>
          <FieldHeader>Assignee</FieldHeader>
          {incident.assignee ? (
            <p>{incident.assignee}</p>
          ) : (
            <p>No assignee yet</p>
          )}
        </div>
        {!!incident.last_seen_time && (
          <div>
            <FieldHeader>Last seen at</FieldHeader>
            <p>
              <TimeAgo date={incident.last_seen_time + "Z"} />
            </p>
            <p className="text-gray-500 text-sm">
              {format(new Date(incident.last_seen_time), formatString)}
            </p>
          </div>
        )}
        {!!incident.start_time && (
          <div>
            <FieldHeader>Started at</FieldHeader>
            <p>
              <TimeAgo date={incident.start_time + "Z"} />
            </p>
            <p className="text-gray-500 text-sm">
              {format(new Date(incident.start_time), formatString)}
            </p>
          </div>
        )}
        {!!incident.rule_fingerprint && (
          <div>
            <FieldHeader>Group by value</FieldHeader>
            <p>{incident.rule_fingerprint}</p>
          </div>
        )}
      </div>
    </div>
  );
}
