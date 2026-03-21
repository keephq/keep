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
import { useI18n } from "@/i18n/hooks/useI18n";

export default function Extraction() {
  const { t } = useI18n();
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
          <PageTitle>{t("rules.extraction.title")}</PageTitle>
          <PageSubtitle>
            {t("rules.extraction.description")}
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
            {t("rules.extraction.addRule")}
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
              <EmptyStateCard icon={ExportIcon} title={t("rules.extraction.messages.noRules")}>
                <Button
                  color="orange"
                  size="md"
                  type="submit"
                  onClick={() => setIsSidePanelOpen(true)}
                  icon={PlusIcon}
                >
                  {t("rules.extraction.addRule")}
                </Button>
              </EmptyStateCard>
            )}
          </div>
        </div>
      </Card>
    </div>
  );
}
