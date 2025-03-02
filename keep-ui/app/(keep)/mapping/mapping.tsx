"use client";
import { Callout, Card } from "@tremor/react";
import CreateOrEditMapping from "./create-or-edit-mapping";
import { useMappings } from "utils/hooks/useMappingRules";
import RulesTable from "./rules-table";
import { MdWarning } from "react-icons/md";
import Loading from "@/app/(keep)/loading";
import { MappingRule } from "./models";
import React, { useEffect, useState } from "react";
import { Button } from "@tremor/react";
import SidePanel from "@/components/SidePanel";
import { PageSubtitle, PageTitle } from "@/shared/ui";
import { PlusCircleIcon } from "@heroicons/react/24/outline";

export default function Mapping() {
  const { data: mappings, isLoading } = useMappings();

  // We use this state to pass the rule that needs to be edited between the CreateNewMapping and the RulesTable Component.
  const [editRule, setEditRule] = useState<MappingRule | null>(null);

  const [isSidePanelOpen, setIsSidePanelOpen] = useState<boolean>(false);

  useEffect(() => {
    if (editRule) {
      setIsSidePanelOpen(true);
    }
  }, [editRule]);

  function handleSidePanelExit(mapping: MappingRule | null) {
    if (mapping) {
      setEditRule(mapping);
    } else {
      setEditRule(null);
      setIsSidePanelOpen(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-row items-center justify-between">
        <div>
          <PageTitle>Mapping</PageTitle>
          <PageSubtitle>
            Enrich alerts with more data from Topology, CSV, JSON and YAMLs
          </PageSubtitle>
        </div>
        <div>
          <Button
            color="orange"
            size="md"
            type="submit"
            onClick={() => setIsSidePanelOpen(true)}
            icon={PlusCircleIcon}
          >
            Create Mapping
          </Button>
        </div>
      </div>
      <Card className="p-0 overflow-hidden">
        <SidePanel
          isOpen={isSidePanelOpen}
          onClose={() => handleSidePanelExit(null)}
          panelWidth="w-1/3"
        >
          <h2 className="text-lg">Configure</h2>
          <p className="text-slate-400">
            Add dynamic context to your alerts with mapping rules
          </p>
          <CreateOrEditMapping
            editRule={editRule}
            editCallback={handleSidePanelExit}
          />
        </SidePanel>

        <div>
          {isLoading ? (
            <Loading />
          ) : mappings && mappings.length > 0 ? (
            <RulesTable
              mappings={mappings}
              editCallback={handleSidePanelExit}
            />
          ) : (
            <Callout
              color="orange"
              title="Mapping rules does not exist"
              icon={MdWarning}
            >
              No mapping rules found. Configure new mapping rule using the
              mapping rules wizard.
            </Callout>
          )}
        </div>
      </Card>
    </div>
  );
}
