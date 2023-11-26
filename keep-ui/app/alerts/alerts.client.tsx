"use client";

import { useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import Loading from "../loading";
import Alerts from "./alerts";
import Pusher from "pusher-js";
import { getApiURL } from "utils/apiUrl";
import { useEffect, useState } from "react";

export default function AlertsPage() {
  const { data: session, status } = useSession();
  const [pusherClient, setPusherClient] = useState<Pusher | null>(null);
  const router = useRouter();

  useEffect(() => {
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
    setPusherClient(pusher);
  }, [session]);

  if (status === "loading") return <Loading />;
  if (pusherClient === null) return <Loading />;
  if (status === "unauthenticated") router.push("/signin");
  if (session && !session.tenantId) router.push("/signin");

  return (
    <Alerts
      accessToken={session?.accessToken!}
      tenantId={session?.tenantId!}
      pusher={pusherClient}
    />
  );
}
