import { Card } from "@tremor/react";
import CreateOrUpdateExtractionRule from "./create-or-update-extraction-rule";

export default function Extraction() {
  return (
    <Card className="p-4 md:p-10 mx-auto">
      <div className="flex divide-x p-2">
        <div className="w-1/3 pr-2.5">
          <CreateOrUpdateExtractionRule />
        </div>
        <div className="w-2/3 pl-2.5">B</div>
      </div>
    </Card>
  );
}
