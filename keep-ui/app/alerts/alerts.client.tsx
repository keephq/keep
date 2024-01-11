"use client";

import { useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import Loading from "../loading";
import Alerts from "./alerts";
import Pusher from "pusher-js";
import { getApiURL } from "utils/apiUrl";
import { useEffect, useState } from "react";
import useSWR from "swr";
import { InternalConfig } from "types/internal-config";
import { fetcher } from "utils/fetcher";

export default function AlertsPage() {
  const { data: session, status } = useSession();
  const {
    data: configData,
    error,
    isLoading,
  } = useSWR<InternalConfig>("/api/config", fetcher, undefined);
  const [pusherClient, setPusherClient] = useState<Pusher | null>(null);
  const router = useRouter();
  const pusherDisabled = configData?.PUSHER_DISABLED === true;

  useEffect(() => {
    if (
      !isLoading &&
      configData &&
      configData.PUSHER_DISABLED !== true &&
      session &&
      pusherClient === null
    ) {
      const pusher = new Pusher(configData.PUSHER_APP_KEY, {
        wsHost: configData.PUSHER_HOST,
        wsPort: configData.PUSHER_PORT,
        forceTLS: false,
        disableStats: true,
        enabledTransports: ["ws", "wss"],
        cluster: configData.PUSHER_CLUSTER || "local",
        channelAuthorization: {
          transport: "ajax",
          endpoint: `${getApiURL()}/pusher/auth`,
          headers: {
            Authorization: `Bearer ${session?.accessToken!}`,
          },
        },
      });
      setPusherClient(pusher);
    }
  }, [session, pusherClient, configData, isLoading]);

  if (status === "loading" || isLoading) return <Loading />;
  if (pusherClient === null && !pusherDisabled) return <Loading />;
  if (status === "unauthenticated") router.push("/signin");
  if (session && !session.tenantId) router.push("/signin");

  return (
    <Alerts
      accessToken={session?.accessToken!}
      tenantId={session?.tenantId!}
      pusher={pusherClient}
      user={session?.user!}
      pusherDisabled={pusherDisabled}
    />
  );
}
