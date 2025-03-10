import React, { useCallback, useRef } from "react";
import { Button } from "@/components/ui";
import Modal from "@/components/ui/Modal";
import { KeepLoader } from "@/shared/ui";
import { useReactToPrint } from "react-to-print";
import { useReportData } from "./use-report-data";
import { IncidentData } from "./models";
import { IncidentsReport } from "./incidents-report";
import { PrinterIcon } from "@heroicons/react/24/outline";

interface GenerateReportModalProps {
  filterCel: string;
  onClose: () => void;
}

export const GenerateReportModal: React.FC<GenerateReportModalProps> = ({
  filterCel,
  onClose,
}) => {
  const { data, isLoading } = useReportData(filterCel);

  const contentRef = useRef<HTMLDivElement>(null);
  const reactToPrintFn = useReactToPrint({
    contentRef,
    documentTitle: "Incidents Report",
  });

  const handlePrint = useCallback(() => reactToPrintFn(), [reactToPrintFn]);

  return (
    <Modal
      title="Incidents Report"
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
                Print
              </Button>
            </div>
          </div>
        )}
      </div>
    </Modal>
  );
};
