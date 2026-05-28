"use client";

import { useRouter } from "next/navigation";
import { useAlerts } from "@/entities/alerts/model";
import { ViewAlertModal } from "@/features/alerts/view-raw-alert";
import { KeepLoader } from "@/shared/ui";
import NotFound from "@/app/(keep)/not-found";

interface AlertFingerprintPageProps {
  fingerprint: string;
}

export function AlertFingerprintPage({ fingerprint }: AlertFingerprintPageProps) {
  const router = useRouter();
  const { useAlertByFingerprint } = useAlerts();
  const { data: alert, error, isLoading, mutate } = useAlertByFingerprint(fingerprint);

  if (isLoading) {
    return <KeepLoader loadingText="Loading alert..." />;
  }

  if (error || !alert) {
    return <NotFound />;
  }

  return (
    <ViewAlertModal
      alert={alert}
      handleClose={() => router.replace("/alerts/feed")}
      mutate={mutate}
    />
  );
}
