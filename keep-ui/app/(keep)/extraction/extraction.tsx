"use client";
import { Callout, Card, Title, Subtitle } from "@tremor/react";
import CreateOrUpdateExtractionRule from "./create-or-update-extraction-rule";
import ExtractionsTable from "./extractions-table";
import { useExtractions } from "utils/hooks/useExtractionRules";
import Loading from "@/app/(keep)/loading";
import { MdWarning } from "react-icons/md";
import { ExtractionRule } from "./model";
import React, { useEffect, useState } from "react";
import { Button } from "@tremor/react";
import SidePanel from "@/components/SidePanel";

export default function Extraction() {
  const { data: extractions, isLoading } = useExtractions();
  const [extractionToEdit, setExtractionToEdit] =
    useState<ExtractionRule | null>(null);

  const [isSidePanelOpen, setIsSidePanelOpen] = useState<boolean>(false);

  useEffect(() => {
    if (extractionToEdit) {
      setIsSidePanelOpen(true);
    }
  }, [extractionToEdit]);

  function handleSidePanelExit(extraction: ExtractionRule | null) {
    if (extraction) {
      setExtractionToEdit(extraction);
    } else {
      setExtractionToEdit(null);
      setIsSidePanelOpen(false);
    }
  }

  return (
    <>
      <div className="flex flex-row items-center justify-between">
        <div className="p-4 md:p-4">
          <Title>Extractions</Title>
          <Subtitle>
            Easily extract more attributes from your alerts using Regex
          </Subtitle>
        </div>
        <div>
          <Button
            color="orange"
            size="xs"
            type="submit"
            onClick={() => setIsSidePanelOpen(true)}
          >
            + Create Extraction
          </Button>
        </div>
      </div>

      <Card className="mt-5 p-4 md:p-10 mx-auto">
        <SidePanel
          isOpen={isSidePanelOpen}
          onClose={() => handleSidePanelExit(null)}
        >
          <div className="pt-6 px-6">
            <CreateOrUpdateExtractionRule
              extractionToEdit={extractionToEdit}
              editCallback={handleSidePanelExit}
            />
          </div>
        </SidePanel>
        <div className="">
          <div className="">
            {isLoading ? (
              <Loading />
            ) : extractions && extractions.length > 0 ? (
              <ExtractionsTable
                extractions={extractions}
                editCallback={handleSidePanelExit}
              />
            ) : (
              <Callout
                color="orange"
                title="Extraction rules does not exist"
                icon={MdWarning}
              >
                No extraction rules found. Configure new extraction rule using
                the + Create Extraction
              </Callout>
            )}
          </div>
        </div>
      </Card>
    </>
  );
}
