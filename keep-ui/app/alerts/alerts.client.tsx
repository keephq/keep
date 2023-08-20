"use client";

import { useSession } from "../../utils/customAuth";
import Loading from "../loading";
import Alerts from "./alerts";

export default function AlertsPage() {
  const { data: session, status } = useSession();

  if (status === "loading") return <Loading />;
  if (status === "unauthenticated") return <div>Unauthenticated...</div>;

  return <Alerts accessToken={session?.accessToken!} />;
}
