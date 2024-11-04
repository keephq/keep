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
import { Badge, Callout, Divider } from "@tremor/react";
import { Link } from "@/components/ui";
import { IncidentChangeStatusSelect } from "@/features/change-incident-status";
import { getIncidentName } from "@/entities/incidents/lib/utils";
import { SameIncidentsOverview } from "@/features/same-incidents-in-the-past";

interface Props {
  incident: IncidentDto;
}

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
      <h3 className="text-gray-500 text-sm">{title}</h3>
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

export default function IncidentOverview({
  incident: initialIncidentData,
}: Props) {
  const { data: fetchedIncident } = useIncident(initialIncidentData.id, {
    fallbackData: initialIncidentData,
    revalidateOnMount: false,
  });
  const incident = fetchedIncident || initialIncidentData;
  const formatString = "dd, MMM yyyy - HH:mm.ss 'UTC'";
  const summary = incident.user_summary || incident.generated_summary;

  return (
    <div className="flex w-full h-full flex-col justify-between">
      <div className="flex flex-col gap-2">
        {incident.merged_into_incident_id && (
          <MergedCallout
            merged_into_incident_id={incident.merged_into_incident_id}
          />
        )}
        {/*TODO: use this magic property to treat children like a children of a parent flex container */}
        <div>
          <h3 className="text-gray-500 text-sm">Status</h3>
          <div>
            <IncidentChangeStatusSelect
              incidentId={incident.id}
              value={incident.status}
            />
          </div>
        </div>
        <div className="flex flex-col gap-2 max-w-3xl">
          <Summary title="Summary" summary={summary} />
          {incident.user_summary && incident.generated_summary ? (
            <Summary
              title="AI version"
              summary={incident.generated_summary}
              collapsable={true}
            />
          ) : null}
        </div>
        <div className="flex flex-col gap-2">
          <h3 className="text-gray-500 text-sm">Involved services</h3>
          <div className="flex flex-wrap gap-1">
            {incident.services.length > 0
              ? incident.services.map((service) => (
                  <Badge key={service} size="sm">
                    {service}
                  </Badge>
                ))
              : "No services involved"}
          </div>
        </div>
        <div>
          <h3 className="text-gray-500 text-sm">Assignee</h3>
          {incident.assignee ? (
            <p>{incident.assignee}</p>
          ) : (
            <p>No assignee yet</p>
          )}
        </div>
        {!!incident.start_time || !!incident.last_seen_time ? (
          <div className="flex gap-4">
            {!!incident.start_time && (
              <div>
                <h3 className="text-gray-500 text-sm">Started at</h3>
                <p className="">
                  {format(new Date(incident.start_time), formatString)}
                </p>
              </div>
            )}
            {!!incident.last_seen_time && (
              <div>
                <h3 className="text-gray-500 text-sm">Last seen at</h3>
                <p>{format(new Date(incident.last_seen_time), formatString)}</p>
              </div>
            )}
          </div>
        ) : null}
        {!!incident.rule_fingerprint && (
          <div>
            <h3 className="text-sm text-gray-500">Group by value</h3>
            <p>{incident.rule_fingerprint}</p>
          </div>
        )}
      </div>
      <Divider />
      <SameIncidentsOverview incident={incident} />
    </div>
  );
}
