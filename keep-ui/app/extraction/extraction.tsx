"use client";
import { Callout, Card } from "@tremor/react";
import CreateOrUpdateExtractionRule from "./create-or-update-extraction-rule";
import ExtractionsTable from "./extractions-table";
import { useExtractions } from "utils/hooks/useExtractionRules";
import Loading from "app/loading";
import { MdWarning } from "react-icons/md";

export default function Extraction() {
  const { data: extractions, isLoading } = useExtractions();
  return (
    <Card className="p-4 md:p-10 mx-auto">
      <div className="flex divide-x p-2">
        <div className="w-1/3 pr-2.5">
          <CreateOrUpdateExtractionRule />
        </div>
        <div className="w-2/3 pl-2.5">
          {isLoading ? (
            <Loading />
          ) : extractions && extractions.length > 0 ? (
            <ExtractionsTable
              extractions={extractions}
              editCallback={() => {}}
            />
          ) : (
            <Callout
              color="orange"
              title="Extraction rules does not exist"
              icon={MdWarning}
            >
              <p className="text-slate-400">No extraction rules found.</p>
              <p className="text-slate-400">
                Configure new extraction rule using the extration rules wizard
                to the left.
              </p>
            </Callout>
          )}
        </div>
      </div>
    </Card>
  );
}
