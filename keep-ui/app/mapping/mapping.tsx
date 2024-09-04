"use client";
import { Badge, Callout, Card } from "@tremor/react";
import CreateOrEditMapping from "./create-or-edit-mapping";
import { useMappings } from "utils/hooks/useMappingRules";
import RulesTable from "./rules-table";
import { MdWarning } from "react-icons/md";
import Loading from "app/loading";
import { MappingRule } from "./models";
import { useState } from "react";

export default function Mapping() {
  const { data: mappings, isLoading } = useMappings();

  // We use this state to pass the rule that needs to be edited between the CreateNewMapping and the RulesTable Component.
  const [editRule, setEditRule] = useState<MappingRule | null>(null);

  return (
    <Card className="mt-10 p-4 md:p-10 mx-auto">
      <div className="flex divide-x p-2">
        <div className="w-1/3 pr-2.5">
          <h2 className="text-lg">Configure</h2>
          <p className="text-slate-400">
            Add dynamic context to your alerts with mapping rules
          </p>
          <CreateOrEditMapping editRule={editRule} editCallback={setEditRule} />
        </div>

        <div className="w-2/3 pl-2.5">
          {isLoading ? (
            <Loading />
          ) : mappings && mappings.length > 0 ? (
            <RulesTable mappings={mappings} editCallback={setEditRule} />
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
      </div>
    </Card>
  );
}
