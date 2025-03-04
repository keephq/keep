"use client";
import { Card } from "@tremor/react";
import CreateOrUpdateExtractionRule from "./create-or-update-extraction-rule";
import ExtractionsTable from "./extractions-table";
import { useExtractions } from "utils/hooks/useExtractionRules";
import {
  KeepLoader,
  PageTitle,
  PageSubtitle,
  EmptyStateCard,
} from "@/shared/ui";
import { ExtractionRule } from "./model";
import React, { useEffect, useState } from "react";
import { Button } from "@tremor/react";
import SidePanel from "@/components/SidePanel";
import { PlusIcon } from "@heroicons/react/20/solid";
import { ExportIcon } from "@/components/icons";

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
            icon={PlusIcon}
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
              <KeepLoader />
            ) : extractions && extractions.length > 0 ? (
              <ExtractionsTable
                extractions={extractions}
                editCallback={handleSidePanelExit}
              />
            ) : (
              <EmptyStateCard icon={ExportIcon} title="No extraction rules yet">
                <Button
                  color="orange"
                  size="md"
                  type="submit"
                  onClick={() => setIsSidePanelOpen(true)}
                  icon={PlusIcon}
                >
                  Create Extraction Rule
                </Button>
              </EmptyStateCard>
            )}
          </div>
        </div>
      </Card>
    </div>
  );
}
