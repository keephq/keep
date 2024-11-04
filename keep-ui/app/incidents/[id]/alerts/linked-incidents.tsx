"use client";

import { getIncidentName } from "@/entities/incidents/lib/utils";
import {
  useIncident,
  useIncidentFutureIncidents,
} from "@/utils/hooks/useIncidents";
import { IncidentDto } from "../../models";
import { useState } from "react";
import ChangeSameIncidentInThePast from "../../incident-change-same-in-the-past";
import Modal from "@/components/ui/Modal";
import { Button } from "@/components/ui/Button";
import { Link } from "@/components/ui";

function FollowingIncident({ incidentId }: { incidentId: string }) {
  const { data: incident } = useIncident(incidentId);

  if (!incident) {
    return null;
  }

  return (
    <div>
      <a className="text-orange-500" href={"/incidents/" + incidentId}>
        {getIncidentName(incident)}
      </a>
    </div>
  );
}

function ManageSameIncidentInThePast({ incident }: { incident: IncidentDto }) {
  const { data: same_incident_in_the_past } = useIncident(
    incident.same_incident_in_the_past_id
  );

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

  return (
    <>
      <h3 className="text-gray-500 text-sm mb-1">Same in the past</h3>
      {same_incident_in_the_past ? (
        <p className="flex items-center gap-2">
          <Link href={"/incidents/" + same_incident_in_the_past.id}>
            {getIncidentName(same_incident_in_the_past)}
          </Link>
          <Button
            color="orange"
            variant="secondary"
            size="xs"
            className="!px-1 !py-0.5"
            onClick={(e) => handleChangeSameIncidentInThePast(e, incident)}
          >
            Change
          </Button>
        </p>
      ) : (
        <p className="flex items-center gap-2">
          No linked incidents
          <Button
            color="orange"
            variant="secondary"
            size="xs"
            className="!px-1 !py-0.5"
            onClick={(e) => handleChangeSameIncidentInThePast(e, incident)}
          >
            Link incident
          </Button>
        </p>
      )}
      {changeSameIncidentInThePast ? (
        <Modal
          isOpen={changeSameIncidentInThePast !== null}
          onClose={() => setChangeSameIncidentInThePast(null)}
          title="Link to the same incident in the past"
          className="w-[600px]"
        >
          <ChangeSameIncidentInThePast
            key={incident.id}
            incident={changeSameIncidentInThePast}
            linkedIncident={same_incident_in_the_past ?? null}
            handleClose={() => setChangeSameIncidentInThePast(null)}
          />
        </Modal>
      ) : null}
    </>
  );
}

export function LinkedIncidents({ incident }: { incident: IncidentDto }) {
  const { data: same_incidents_in_the_future } = useIncidentFutureIncidents(
    incident.id
  );

  return (
    <div>
      <header className="flex flex-col mb-2">
        <h2 className="text-md font-semibold">Similar incidents</h2>
        <p className="text-sm">
          Link the same incident from the past to help the AI classifier
        </p>
      </header>
      <ManageSameIncidentInThePast incident={incident} />
      {same_incidents_in_the_future &&
        same_incidents_in_the_future.items.length > 0 && (
          <div>
            <h3 className="text-gray-500 text-sm">Following incidents</h3>
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
  );
}
