"use client";

import type { IncidentDto } from "@/entities/incidents/model";
import React from "react";
import { useIncident } from "@/utils/hooks/useIncidents";
import { Disclosure } from "@headlessui/react";
import { IoChevronDown } from "react-icons/io5";
import remarkRehype from "remark-rehype";
import rehypeRaw from "rehype-raw";
import Markdown from "react-markdown";
import { Badge, Callout } from "@tremor/react";
import { Link } from "@/components/ui";
import { IncidentChangeStatusSelect } from "@/features/change-incident-status";
import { getIncidentName } from "@/entities/incidents/lib/utils";
import { DateTimeField, FieldHeader } from "@/shared/ui";
import {
  SameIncidentField,
  FollowingIncidents,
} from "@/features/same-incidents-in-the-past/";
import { StatusIcon } from "@/entities/incidents/ui/statuses";
import clsx from "clsx";

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
      <Disclosure as="div" className={clsx("space-y-1", className)}>
        <Disclosure.Button>
          {({ open }) => (
            <h4 className="text-gray-500 text-sm inline-flex justify-between items-center gap-1">
              <span>{title}</span>
              <IoChevronDown
                className={clsx({ "rotate-180": open }, "text-slate-400")}
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
    //TODO: suggest generate summary if it's empty
    summary ? <div>{formatedSummary}</div> : <p>No summary yet</p>
  );
}

function MergedCallout({
  merged_into_incident_id,
  className,
}: {
  merged_into_incident_id: string;
  className?: string;
}) {
  const { data: merged_incident } = useIncident(merged_into_incident_id);

  if (!merged_incident) {
    return null;
  }

  return (
    <Callout
      // @ts-ignore
      title={
        <div>
          <p>This incident was merged into</p>
          <Link
            icon={() => (
              <StatusIcon className="!p-0" status={merged_incident.status} />
            )}
            href={`/incidents/${merged_incident?.id}`}
          >
            {getIncidentName(merged_incident)}
          </Link>
        </div>
      }
      color="purple"
      className={className}
    />
  );
}

export function IncidentOverview({ incident: initialIncidentData }: Props) {
  const { data: fetchedIncident } = useIncident(initialIncidentData.id, {
    fallbackData: initialIncidentData,
    revalidateOnMount: false,
  });
  const incident = fetchedIncident || initialIncidentData;
  const summary = incident.user_summary || incident.generated_summary;
  // Why do we have "null" in services?
  const notNullServices = incident.services.filter(
    (service) => service !== "null"
  );

  return (
    // Adding padding bottom to visually separate from the tabs
    <div className="flex gap-6 items-start w-full pb-4 text-tremor-default">
      <div className="basis-2/3 grow">
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          <div className="max-w-2xl">
            <FieldHeader>Summary</FieldHeader>
            <Summary title="Summary" summary={summary} />
            {incident.user_summary && incident.generated_summary ? (
              <Summary
                title="AI version"
                summary={incident.generated_summary}
                collapsable={true}
              />
            ) : null}
            {incident.merged_into_incident_id && (
              <MergedCallout
                className="inline-block mt-2"
                merged_into_incident_id={incident.merged_into_incident_id}
              />
            )}
          </div>
          <div className="flex flex-col gap-2">
            <FieldHeader>Involved services</FieldHeader>
            {notNullServices.length > 0 ? (
              <div className="flex flex-wrap gap-1">
                {notNullServices.map((service) => (
                  <Badge key={service} size="sm">
                    {service}
                  </Badge>
                ))}
              </div>
            ) : (
              "No services involved"
            )}
          </div>
          <div>
            <SameIncidentField incident={incident} />
          </div>
          <div>
            <FollowingIncidents incident={incident} />
          </div>
        </div>
      </div>
      <div className="pr-10 grid grid-cols-1 xl:grid-cols-2 gap-4">
        <div className="xl:col-span-2">
          <FieldHeader>Status</FieldHeader>
          <IncidentChangeStatusSelect
            incidentId={incident.id}
            value={incident.status}
          />
        </div>
        {!!incident.last_seen_time && (
          <div>
            <FieldHeader>Last seen at</FieldHeader>
            <DateTimeField date={incident.last_seen_time} />
          </div>
        )}
        {!!incident.start_time && (
          <div>
            <FieldHeader>Started at</FieldHeader>
            <DateTimeField date={incident.start_time} />
          </div>
        )}
        <div>
          <FieldHeader>Assignee</FieldHeader>
          {incident.assignee ? (
            <p>{incident.assignee}</p>
          ) : (
            <p>No assignee yet</p>
          )}
        </div>
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
