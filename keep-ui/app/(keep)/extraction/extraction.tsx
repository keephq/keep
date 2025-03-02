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
import { PlusCircleIcon } from "@heroicons/react/24/outline";
import { PageSubtitle } from "@/shared/ui";
import { PageTitle } from "@/shared/ui";

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
    <div className="flex flex-col gap-6">
      <div className="flex flex-row items-center justify-between">
        <div>
          <PageTitle>Extractions</PageTitle>
          <PageSubtitle>
            Easily extract more attributes from your alerts using Regex
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
            Create Extraction
          </Button>
        </div>
      </div>

      <Card className="p-0 overflow-hidden">
        <SidePanel
          isOpen={isSidePanelOpen}
          onClose={() => handleSidePanelExit(null)}
        >
          <CreateOrUpdateExtractionRule
            extractionToEdit={extractionToEdit}
            editCallback={handleSidePanelExit}
          />
        </SidePanel>
        <div>
          <div>
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
    </div>
  );
}
