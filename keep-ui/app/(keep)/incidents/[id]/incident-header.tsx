"use client";

import {
  useIncidentActions,
  type IncidentDto,
} from "@/entities/incidents/model";
import { Badge, Button, Icon, Subtitle } from "@tremor/react";
import { Link } from "@/components/ui";
import { ArrowRightIcon } from "@heroicons/react/16/solid";
import { MdBlock, MdDone, MdModeEdit, MdPlayArrow } from "react-icons/md";
import React, { useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { ManualRunWorkflowModal } from "@/features/workflows/manual-run-workflow";
import { CreateOrUpdateIncidentForm } from "features/incidents/create-or-update-incident";
import Modal from "@/components/ui/Modal";
import { getIncidentName } from "@/entities/incidents/lib/utils";
import { useIncident } from "@/utils/hooks/useIncidents";
import { IncidentOverview } from "./incident-overview";
import { CopilotKit } from "@copilotkit/react-core";
import { TbInfoCircle, TbTopologyStar3 } from "react-icons/tb";
import { useConfig } from "@/utils/hooks/useConfig";
import { TicketingIncidentOptions } from "./ticketing-incident-options";
import { useTranslations } from "next-intl";

export function IncidentHeader({
  incident: initialIncidentData,
}: {
  incident: IncidentDto;
}) {
  const t = useTranslations("incidents");
  const { data: fetchedIncident } = useIncident(initialIncidentData.id, {
    fallbackData: initialIncidentData,
    revalidateOnMount: false,
  });
  const { deleteIncident, confirmPredictedIncident } = useIncidentActions();
  const incident = fetchedIncident || initialIncidentData;
  const { data: config } = useConfig();

  const router = useRouter();
  const pathname = usePathname();

  const [isFormOpen, setIsFormOpen] = useState<boolean>(false);

  const [runWorkflowModalIncident, setRunWorkflowModalIncident] =
    useState<IncidentDto | null>();

  const handleCloseForm = () => {
    setIsFormOpen(false);
  };

  const handleFinishEdit = () => {
    setIsFormOpen(false);
  };
  const handleRunWorkflow = () => {
    setRunWorkflowModalIncident(incident);
  };

  const handleStartEdit = () => {
    setIsFormOpen(true);
  };

  const pathNameCapitalized = pathname
    .split("/")
    .pop()
    ?.replace(/^[a-z]/, (match) => match.toUpperCase());

  return (
    <CopilotKit runtimeUrl="/api/copilotkit">
      <header className="flex flex-col mb-1">
        <div className="flex flex-row justify-between items-end mb-2.5">
          <div>
            <Subtitle className="text-sm">
              <Link href="/incidents">{t("allIncidents")}</Link>{" "}
              <Icon icon={ArrowRightIcon} color="gray" size="xs" />{" "}
              {incident.is_candidate ? "" : `${t("possible")} `}
              {getIncidentName(incident)}
              {pathNameCapitalized && (
                <>
                  <Icon icon={ArrowRightIcon} color="gray" size="xs" />
                  {pathNameCapitalized}
                </>
              )}
            </Subtitle>
          </div>

          {!incident.is_candidate && (
            <div className="flex">
              {config?.KEEP_TICKETING_ENABLED && (
                <TicketingIncidentOptions
                  incident={incident}
                />
              )}
              <Button
                color="orange"
                size="xs"
                variant="secondary"
                className="!py-0.5 mr-2"
                icon={MdPlayArrow}
                onClick={(e: React.MouseEvent) => {
                  e.preventDefault();
                  e.stopPropagation();
                  handleRunWorkflow();
                }}
              >
                {t("actions.runWorkflow")}
              </Button>
              <Button
                color="orange"
                size="xs"
                variant="secondary"
                className="!py-0.5"
                icon={MdModeEdit}
                onClick={(e: React.MouseEvent) => {
                  e.preventDefault();
                  e.stopPropagation();
                  handleStartEdit();
                }}
              >
                {t("actions.editIncident")}
              </Button>
            </div>
          )}
        </div>
        <div className="flex justify-start items-center text-sm gap-2">
          <div className="prose-2xl flex-grow flex gap-1">
            {incident.incident_type == "topology" && (
              <Badge
                color="blue"
                size="xs"
                icon={TbTopologyStar3}
                tooltip={t("messages.topologyTooltip")}
              >
                {t("messages.topology")}
              </Badge>
            )}
            {incident.rule_is_deleted && (
              <Badge
                color="orange"
                size="xs"
                icon={TbInfoCircle}
                tooltip={t("messages.orphanedTooltip", { ruleName: incident.rule_name })}
              >
                {t("messages.orphaned")}
              </Badge>
            )}
          </div>
          {incident.is_candidate && (
            <div className="space-x-1 flex flex-row items-center justify-center">
              <Button
                color="orange"
                size="xs"
                tooltip={t("messages.confirmIncident")}
                variant="secondary"
                title={t("actions.confirm")}
                icon={MdDone}
                onClick={(e: React.MouseEvent) => {
                  e.preventDefault();
                  e.stopPropagation();
                  confirmPredictedIncident(incident.id!);
                }}
              >
                {t("actions.confirm")}
              </Button>
              <Button
                color="red"
                size="xs"
                variant="secondary"
                tooltip={t("actions.discard")}
                icon={MdBlock}
                onClick={async (e: React.MouseEvent) => {
                  e.preventDefault();
                  e.stopPropagation();
                  const success = await deleteIncident(incident.id);
                  if (success) {
                    router.push("/incidents");
                  }
                }}
              />
            </div>
          )}
        </div>
      </header>
      <IncidentOverview incident={incident} />
      <Modal
        isOpen={isFormOpen}
        onClose={handleCloseForm}
        className="w-[600px]"
        title={t("actions.editIncident")}
      >
        <CreateOrUpdateIncidentForm
          incidentToEdit={incident}
          exitCallback={handleFinishEdit}
        />
      </Modal>
      <ManualRunWorkflowModal
        incident={runWorkflowModalIncident}
        onClose={() => setRunWorkflowModalIncident(null)}
      />
    </CopilotKit>
  );
}
