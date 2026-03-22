import { useI18n } from "@/i18n/hooks/useI18n";
import { Button } from "@/components/ui";
import { useIncidentActions } from "@/entities/incidents/model/useIncidentActions";
import { SplitIncidentAlertsModal } from "features/incidents/split-incident-alerts";
import { useState } from "react";
import { LiaElementor, LiaUnlinkSolid } from "react-icons/lia";
import { useRouter } from "next/navigation";

export function IncidentAlertsActions({
  incidentId,
  selectedFingerprints,
  resetAlertsSelection,
}: {
  incidentId: string;
  selectedFingerprints: string[];
  resetAlertsSelection: () => void;
}) {
  const [isSplitModalOpen, setIsSplitModalOpen] = useState(false);
  const { unlinkAlertsFromIncident } = useIncidentActions();
  const router = useRouter();
  const { t } = useI18n();

  return (
    <>
      <div className="flex gap-2 justify-end mb-2.5">
        <Button
          variant="primary"
          onClick={() => setIsSplitModalOpen(true)}
          disabled={selectedFingerprints.length === 0}
        >
          {t("incidents.alerts.split")}
        </Button>
        <Button
          variant="destructive"
          icon={LiaUnlinkSolid}
          onClick={async () => {
            await unlinkAlertsFromIncident(incidentId, selectedFingerprints);
            resetAlertsSelection();
          }}
          disabled={selectedFingerprints.length === 0}
        >
          {t("incidents.alerts.unlink")}
        </Button>
        <Button
          variant="secondary"
          icon={LiaElementor}
          onClick={() => {
            const cel = encodeURIComponent(`incident.id=="${incidentId}"`)
            router.push(`/alerts/feed?cel=${cel}`);
          }}
        >
          {t("incidents.alerts.viewInFeed")}
        </Button>
      </div>
      {isSplitModalOpen && (
        <SplitIncidentAlertsModal
          sourceIncidentId={incidentId}
          alertFingerprints={selectedFingerprints}
          handleClose={() => setIsSplitModalOpen(false)}
          onSuccess={resetAlertsSelection}
        />
      )}
    </>
  );
}
