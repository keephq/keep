"use client";

import { useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import { Loading } from "@/components/Loading";
import Alerts from "./alerts";
import { AlertDto } from "@/app/alerts/models";

type AlertsPageProps = {
  presetName: string;
  initialAlerts: AlertDto[] | null;
};

export default function AlertsPage({
  presetName,
  initialAlerts,
}: AlertsPageProps) {
  const { data: session, status } = useSession();

  const router = useRouter();

  if (status === "loading") {
    return <Loading />;
  }

  if (status === "unauthenticated") {
    router.push("/signin");
  }

  if (session && !session.tenantId) {
    router.push("/signin");
  }

  return <Alerts presetName={presetName} initialAlerts={initialAlerts} />;
}
