import { IncidentDto } from "../models";
import Modal from "@/components/ui/Modal";
import React, { useState } from "react";
import {
  useIncident,
  useIncidentFutureIncidents,
} from "@/utils/hooks/useIncidents";
import { format } from "date-fns";
import { Disclosure } from "@headlessui/react";
import classNames from "classnames";
import { IoChevronDown } from "react-icons/io5";
import ChangeSameIncidentInThePast from "@/app/incidents/incident-change-same-in-the-past";
import remarkRehype from "remark-rehype";
import rehypeRaw from "rehype-raw";
import Markdown from "react-markdown";
import { Callout } from "@tremor/react";
import { Link } from "@/components/ui";
import { IncidentChangeStatusSelect } from "@/features/change-incident-status";

interface Props {
  incident: IncidentDto;
}

function FollowingIncident({ incidentId }: { incidentId: string }) {
  const { data: incident } = useIncident(incidentId);
  return (
    <div>
      <a className="text-orange-500" href={"/incidents/" + incidentId}>
        {incident?.user_generated_name || incident?.ai_generated_name}
      </a>
    </div>
  );
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
      {summary ? <p>{formatedSummary}</p> : <p>No summary yet</p>}
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
          {merged_incident?.user_generated_name ||
            merged_incident?.ai_generated_name}
        </Link>
      </p>
    </Callout>
  );
}

export default function IncidentOverview({ incident }: Props) {
  const { mutate } = useIncident(incident.id);

  const [changeSameIncidentInThePast, setChangeSameIncidentInThePast] =
    useState<IncidentDto | null>();

  const handleChangeSameIncidentInThePast = (
    e: React.MouseEvent,
    incident: IncidentDto
  ) => {
    e.preventDefault();
    e.stopPropagation();
    setChangeSameIncidentInThePast(incident);
  };

  const formatString = "dd, MMM yyyy - HH:mm.ss 'UTC'";
  const summary = incident.user_summary || incident.generated_summary;
  const { data: same_incident_in_the_past } = useIncident(
    incident.same_incident_in_the_past_id
  );
  const { data: same_incidents_in_the_future } = useIncidentFutureIncidents(
    incident.id
  );

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
              onChange={(status) => {
                mutate();
              }}
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
        <div>
          <h3 className="text-gray-500 text-sm">Assignee</h3>
          {incident.assignee ? (
            <p>{incident.assignee}</p>
          ) : (
            <p>No assignee yet</p>
          )}
        </div>
        <div>
          <div className="flex flex-row gap-4">
            <div>
              <h3 className="text-gray-500 text-sm">
                Same incident in the past
              </h3>
              {same_incident_in_the_past ? (
                <p>
                  <a
                    className="text-orange-500"
                    href={"/incidents/" + same_incident_in_the_past.id}
                  >
                    {same_incident_in_the_past.user_generated_name ||
                      same_incident_in_the_past.ai_generated_name}
                  </a>{" "}
                  (
                  <a
                    href="#"
                    onClick={(e) =>
                      handleChangeSameIncidentInThePast(e, incident)
                    }
                    className="cursor-pointer text-orange-500"
                  >
                    edit
                  </a>
                  )
                </p>
              ) : (
                <p>
                  No linked incidents. Link same incident from the past to help
                  the AI classifier. 🤔 (
                  <a
                    onClick={(e) =>
                      handleChangeSameIncidentInThePast(e, incident)
                    }
                    className="cursor-pointer text-orange-500"
                  >
                    click to link
                  </a>
                  )
                </p>
              )}
            </div>
            <div></div>
          </div>
          {same_incidents_in_the_future &&
            same_incidents_in_the_future.items.length > 0 && (
              <div>
                <h3 className="text-gray-500 text-sm">Following Incidents</h3>
                <ul>
                  {same_incidents_in_the_future.items.map((item) => (
                    <li key={item.id}>
                      <FollowingIncident incidentId={item.id} />
                    </li>
                  ))}
                </ul>
              </div>
            )}
        </div>
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
        <div>
          {!!incident.rule_fingerprint && (
            <>
              <h3 className="text-sm text-gray-500">Group by value</h3>
              <p>{incident.rule_fingerprint}</p>
            </>
          )}
        </div>
      </div>
      {changeSameIncidentInThePast ? (
        <Modal
          isOpen={changeSameIncidentInThePast !== null}
          onClose={() => setChangeSameIncidentInThePast(null)}
          title="Link to the same incident in the past"
          className="w-[600px]"
        >
          <ChangeSameIncidentInThePast
            incident={changeSameIncidentInThePast}
            mutate={mutate}
            handleClose={() => setChangeSameIncidentInThePast(null)}
          />
        </Modal>
      ) : null}
    </div>
  );
}
