"use client";

import { useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import Loading from "../loading";
import Alerts from "./alerts";

type AlertsPageProps = {
  presetName: string;
};

export default function AlertsPage({ presetName }: AlertsPageProps) {
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

  return <Alerts presetName={presetName} />;
}
