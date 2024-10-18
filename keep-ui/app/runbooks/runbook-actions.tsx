import { useState } from "react";
import { Button } from "@tremor/react";
import { RunbookDto } from "./models";
import { PlusIcon } from "@radix-ui/react-icons";
import RunbookAssociateIncidentModal from "./runbook-associate-incident-modal";

interface Props {
  selectedRowIds: string[];
  runbooks: RunbookDto[];
  clearRowSelection: () => void;
}

export default function RunbookActions({
  selectedRowIds,
  runbooks,
  clearRowSelection,
}: Props) {
  const [isIncidentSelectorOpen, setIsIncidentSelectorOpen] =
    useState<boolean>(false);

  const selectedRunbooks = runbooks.filter((_runbook, index) =>
    selectedRowIds.includes(index.toString())
  );

  const showIncidentSelector = () => {
    setIsIncidentSelectorOpen(true);
  };
  const hideIncidentSelector = () => {
    setIsIncidentSelectorOpen(false);
  };

  const handleSuccessfulRunbooksAssociation = () => {
    hideIncidentSelector();
    clearRowSelection();
  };

  return (
    <div className="w-full flex justify-end items-center">
      <Button
        icon={PlusIcon}
        size="xs"
        color="orange"
        className="ml-2.5"
        onClick={showIncidentSelector}
        tooltip="Associate events with incident"
      >
        Associate with incident
      </Button>
      <RunbookAssociateIncidentModal
        isOpen={isIncidentSelectorOpen}
        runbooks={selectedRunbooks}
        handleSuccess={handleSuccessfulRunbooksAssociation}
        handleClose={hideIncidentSelector}
      />
    </div>
  );
}
