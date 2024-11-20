"use client";

import { useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import Loading from "../(keep)/loading";
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
    console.log("unauthenticated");
    router.push("/signin");
  }

  if (session && !session.tenantId) {
    console.log("no tenantId");
    router.push("/signin");
  }

  return <Alerts presetName={presetName} />;
}
