import { Card } from "@tremor/react";
import CreateNewMapping from "./create-new-mapping";
import { useMappings } from "utils/hooks/useMappingRules";

export default function Page() {
  const { data: mappings, mutate } = useMappings();

  return (
    <Card className="p-4 md:p-10 mx-auto">
      <div className="flex divide-x p-2">
        <div className="w-1/3 pr-2.5">
          <h2 className="text-lg">Configure</h2>
          <p className="text-slate-400">
            Add dynamic context to your alerts with mapping rules
          </p>
          <CreateNewMapping mutate={mutate} />
        </div>

        <div className="w-2/3 pl-2.5">
          <h2 className="text-lg">Rules</h2>
          {mappings && mappings.length > 0 ? <>Rules!</> : <>No Rules!</>}
        </div>
      </div>
    </Card>
  );
}

export const metadata = {
  title: "Keep - Alert Mapping",
  description: "Add dynamic context to your alerts with mapping",
};
