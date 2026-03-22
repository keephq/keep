import React, { useCallback, useRef } from "react";
import { Button } from "@/components/ui";
import Modal from "@/components/ui/Modal";
import { KeepLoader } from "@/shared/ui";
import { useReactToPrint } from "react-to-print";
import { useReportData } from "./use-report-data";
import { IncidentData } from "./models";
import { IncidentsReport } from "./incidents-report";
import { PrinterIcon } from "@heroicons/react/24/outline";
import { useI18n } from "@/i18n/hooks/useI18n";

interface GenerateReportModalProps {
  filterCel: string;
  onClose: () => void;
}

export const GenerateReportModal: React.FC<GenerateReportModalProps> = ({
  filterCel,
  onClose,
}) => {
  const { data, isLoading } = useReportData(filterCel);
  const { t } = useI18n();

  const contentRef = useRef<HTMLDivElement>(null);
  const reactToPrintFn = useReactToPrint({
    contentRef,
    documentTitle: "Incidents Report",
  });

  const handlePrint = useCallback(() => reactToPrintFn(), [reactToPrintFn]);

  return (
    <Modal
      title={t("incidents.report.title")}
      className="min-w-[80vw] h-[80vh]"
      isOpen={true}
      onClose={onClose}
    >
      <div className="w-full h-full">
        {isLoading && <KeepLoader />}
        {!isLoading && (
          <div className="flex flex-col w-full h-full">
            <div className="flex-1 overflow-auto">
              <div ref={contentRef}>
                <IncidentsReport incidentsReportData={data as IncidentData} />
              </div>
            </div>
            <div className="flex justify-end p-6 border-teal-100 border-t">
              <Button
                color="orange"
                variant="primary"
                size="md"
                icon={PrinterIcon}
                onClick={handlePrint}
              >
                {t("incidents.report.print")}
              </Button>
            </div>
          </div>
        )}
      </div>
    </Modal>
  );
};
