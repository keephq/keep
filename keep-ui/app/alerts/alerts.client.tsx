"use client";

import { useRouter } from "next/navigation";
import { useSession } from "next-auth/react"
import Loading from "../loading";
import Alerts from "./alerts";

export default function AlertsPage() {
  debugger;
  const { data: session, status } = useSession();
  const router = useRouter();

  if (status === "loading") return <Loading />;
  if (status === "unauthenticated") router.push("/signin");

  return (
    <Alerts accessToken={session?.accessToken!} tenantId={session?.tenantId!} />
  );
}
