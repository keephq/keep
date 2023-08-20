"use client";

import { GlobeAltIcon } from "@heroicons/react/24/outline";
import { Card, Icon, Subtitle, Title } from "@tremor/react";
import Loading from "app/loading";
import useSWR from "swr";
import { getApiURL } from "utils/apiUrl";
import { useSession } from "utils/customAuth";
import { fetcher } from "utils/fetcher";

interface Webhook {
  webhookApi: string;
  apiKey: string;
}

export const WebhookSettings = () => {
  const { data: session, status } = useSession();
  const apiUrl = getApiURL();
  const { data, error, isLoading } = useSWR<Webhook>(
    `${apiUrl}/settings/webhook`,
    (url) => fetcher(url, session?.accessToken!)
  );

  if (status === "loading") return <Loading />;
  if (status === "unauthenticated") return <div>Unauthenticated...</div>;
  if (error) return <div>{error}</div>;
  if (isLoading) return <Loading />;

  return (
    <div className="mt-2.5">
      <Title>Webhook Settings</Title>
      <Subtitle>View your tenant webhook settings</Subtitle>
      <Card className="mt-2.5">
        <Icon variant="light" icon={GlobeAltIcon} size="lg" color="orange" />
        <Title className="mt-6">URL: {data?.webhookApi}</Title>
        <Subtitle className="mt-2">API Key: {data?.apiKey}</Subtitle>
      </Card>
    </div>
  );
};
