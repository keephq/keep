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

interface Props {
  accessToken: string;
}

export default function WebhookSettings({ accessToken }: Props) {
  const apiUrl = getApiURL();
  const { data, error, isLoading } = useSWR<Webhook>(
    `${apiUrl}/settings/webhook`,
    (url) => fetcher(url, accessToken)
  );

  if (!data || isLoading) return <Loading />;
  if (error) return <div>{error.message}</div>;

  return (
    <div className="mt-10">
      <Title>Webhook Settings</Title>
      <Subtitle>View your tenant webhook settings</Subtitle>
      <Card className="mt-2.5">
        <Icon variant="light" icon={GlobeAltIcon} size="lg" color="orange" />
        <Title className="mt-6">URL: {data?.webhookApi}</Title>
        <Subtitle className="mt-2">API Key: {data?.apiKey}</Subtitle>
      </Card>
    </div>
  );
}
