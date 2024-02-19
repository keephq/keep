"use client";
import { Badge, Card } from "@tremor/react";
import CreateNewMapping from "./create-new-mapping";
import { useMappings } from "utils/hooks/useMappingRules";
export default function Mapping() {
  const { data: mappings, mutate } = useMappings();

  return (
    <Card className="p-4 md:p-10 mx-auto">
      <Badge color="orange" size="xs" tooltip="Slack us if something isn't working properly :)" className="absolute top-[-10px] left-[-10px]">Beta</Badge>
      <div className="flex divide-x p-2">
        <div className="w-1/3 pr-2.5">
          <h2 className="text-lg">Configure</h2>
          <p className="text-slate-400">
            Add dynamic context to your alerts with mapping rules
          </p>
          <CreateNewMapping />
        </div>

        <div className="w-2/3 pl-2.5">
          <h2 className="text-lg">Rules</h2>
          {mappings && mappings.length > 0 ? <>Rules!</> : <>No Rules!</>}
        </div>
      </div>
    </Card>
  );
}
