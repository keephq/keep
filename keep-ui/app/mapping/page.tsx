import { Card } from "@tremor/react";
import CreateNewMapping from "./create-new-mapping";

export default function Page() {
  return (
    <Card className="mt-10 p-4 md:p-10 mx-auto">
      <div className="flex divide-x p-2">
        <div className="w-1/3">
          <h2 className="text-lg">Configure</h2>
          <p className="text-slate-400">
            Add dynamic context to your alerts with mapping rules
          </p>
          <CreateNewMapping />
        </div>

        <div className="w-2/3 pl-2.5">
          <h2 className="text-lg">Rules</h2>
        </div>
      </div>
    </Card>
  );
}

export const metadata = {
  title: "Keep - Alert Mapping",
  description: "Add dynamic context to your alerts with mapping",
};
