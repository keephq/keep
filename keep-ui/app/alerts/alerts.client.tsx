"use client";

import { useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import Loading from "../loading";
import Alerts from "./alerts";
import Pusher from "pusher-js";
import { getApiURL } from "utils/apiUrl";

export default function AlertsPage() {
  const { data: session, status } = useSession();
  const router = useRouter();

  if (status === "loading") return <Loading />;
  if (status === "unauthenticated") router.push("/signin");
  if (session && !session.tenantId) router.push("/signin");

  const pusher = new Pusher(process.env.NEXT_PUBLIC_PUSHER_APP_KEY!, {
    wsHost: process.env.NEXT_PUBLIC_PUSHER_HOST,
    wsPort: process.env.NEXT_PUBLIC_PUSHER_PORT
      ? parseInt(process.env.NEXT_PUBLIC_PUSHER_PORT)
      : undefined,
    forceTLS: false,
    disableStats: true,
    enabledTransports: ["ws", "wss"],
    cluster: process.env.NEXT_PUBLIC_PUSHER_CLUSTER || "local",
    channelAuthorization: {
      transport: "ajax",
      endpoint: `${getApiURL()}/pusher/auth`,
      headers: {
        Authorization: `Bearer ${session?.accessToken!}`,
      },
    },
  });

  return (
    <Alerts
      accessToken={session?.accessToken!}
      tenantId={session?.tenantId!}
      pusher={pusher}
    />
  );
}
