import { Button } from "@/components/ui/Button";
import { Link } from "@/components/ui";
import { getIncidentName } from "@/entities/incidents/lib/utils";
import { IncidentDto } from "@/entities/incidents/model";
import { FieldHeader } from "@/shared/ui";
import { useIncident } from "@/utils/hooks/useIncidents";
import { useState } from "react";
import Modal from "@/components/ui/Modal";
import { ChangeSameIncidentInThePastForm } from "./change-same-incident-in-the-past-form";
import { StatusIcon } from "@/entities/incidents/ui/statuses";
import { useI18n } from "@/i18n/hooks/useI18n";

export function SameIncidentField({ incident }: { incident: IncidentDto }) {
  const { t } = useI18n();
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
      <FieldHeader>{t("incidents.sameIncident.sameInThePast")}</FieldHeader>
      {same_incident_in_the_past ? (
        <p className="flex gap-2">
          <Link
            icon={() => (
              <StatusIcon
                className="!p-0 -mb-0.5"
                status={same_incident_in_the_past.status}
              />
            )}
            href={"/incidents/" + same_incident_in_the_past.id}
          >
            {getIncidentName(same_incident_in_the_past)}
          </Link>
          <Button
            color="orange"
            variant="secondary"
            size="xs"
            className="!px-1 !py-0.5"
            onClick={(e) => handleChangeSameIncidentInThePast(e, incident)}
          >
            {t("incidents.sameIncident.change")}
          </Button>
        </p>
      ) : (
        <>
          <p className="flex items-baseline gap-2">
            {t("incidents.sameIncident.noLinkedIncidents")}
            <Button
              color="orange"
              variant="secondary"
              size="xs"
              className="!px-1 !py-0.5"
              onClick={(e) => handleChangeSameIncidentInThePast(e, incident)}
            >
              {t("incidents.sameIncident.linkIncident")}
            </Button>
          </p>
          <p className="text-sm text-tremor-content-subtle">
            {t("incidents.sameIncident.linkHelpText")}
          </p>
        </>
      )}
      {changeSameIncidentInThePast ? (
        <Modal
          isOpen={changeSameIncidentInThePast !== null}
          onClose={() => setChangeSameIncidentInThePast(null)}
          title={t("incidents.sameIncident.linkModalTitle")}
          className="w-[600px]"
        >
          <ChangeSameIncidentInThePastForm
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
