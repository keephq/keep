"use client";
import { Badge, Callout, Card } from "@tremor/react";
import CreateOrUpdateExtractionRule from "./create-or-update-extraction-rule";
import ExtractionsTable from "./extractions-table";
import { useExtractions } from "utils/hooks/useExtractionRules";
import Loading from "app/loading";
import { MdWarning } from "react-icons/md";
import { useState } from "react";
import { ExtractionRule } from "./model";

export default function Extraction() {
  const { data: extractions, isLoading } = useExtractions();
  const [extractionToEdit, setExtractionToEdit] =
    useState<ExtractionRule | null>(null);
  return (
    <Card className="p-4 md:p-10 mx-auto">
      <Badge
        color="orange"
        size="xs"
        tooltip="Slack us if something isn't working properly :)"
        className="absolute top-[-10px] left-[-10px]"
      >
        Beta
      </Badge>
      <div className="flex divide-x p-2">
        <div className="w-1/3 pr-2.5">
          <CreateOrUpdateExtractionRule
            extractionToEdit={extractionToEdit}
            editCallback={setExtractionToEdit}
          />
        </div>
        <div className="w-2/3 pl-2.5">
          {isLoading ? (
            <Loading />
          ) : extractions && extractions.length > 0 ? (
            <ExtractionsTable
              extractions={extractions}
              editCallback={setExtractionToEdit}
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
