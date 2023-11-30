"use client";

import { GlobeAltIcon, PlayIcon } from "@heroicons/react/24/outline";
import { Button, Card, Icon, Subtitle, Title } from "@tremor/react";
import Loading from "app/loading";
import { useRouter } from "next/navigation";
import { CopyBlock, a11yLight } from "react-code-blocks";
import useSWR from "swr";
import { getApiURL } from "utils/apiUrl";
import { fetcher } from "utils/fetcher";

interface Webhook {
  webhookApi: string;
  apiKey: string;
  modelSchema: any;
}

interface Props {
  accessToken: string;
  selectedTab: string;
}

export default function WebhookSettings({ accessToken, selectedTab }: Props) {
  const apiUrl = getApiURL();
  const { data, error, isLoading } = useSWR<Webhook>(
    selectedTab === "webhook" ? `${apiUrl}/settings/webhook` : null,
    (url) => fetcher(url, accessToken),
    { revalidateOnFocus: false }
  );
  const router = useRouter();

  if (!data || isLoading) return <Loading />;
  if (error) return <div>{error.message}</div>;

  const example = data.modelSchema.examples[0] as any;
  example.lastReceived = new Date().toISOString();

  const code = `curl --location '${data.webhookApi}' \\
  --header 'Content-Type: application/json' \\
  --header 'Accept: application/json' \\
  --header 'X-API-KEY: ${data.apiKey}' \\
  --data '${JSON.stringify(example, null, 2)}'`;

  const copyBlockProps = {
    theme: { ...a11yLight },
    customStyle: {
      height: "450px",
      overflowY: "scroll",
    },
    language: "shell",
    text: code,
    codeBlock: true,
    showLineNumbers: false,
  };

  const tryNow = async () => {
    var myHeaders = new Headers();
    myHeaders.append("Content-Type", "application/json");
    myHeaders.append("Accept", "application/json");
    myHeaders.append("X-API-KEY", data.apiKey);

    var raw = JSON.stringify(example);

    const requestOptions = {
      method: "POST",
      headers: myHeaders,
      body: raw,
    };

    const resp = await fetch(data.webhookApi, requestOptions);
    if (resp.ok) {
      router.push("/alerts");
    } else {
      alert("Something went wrong! Please try again.");
    }
  };

  return (
    <div className="mt-10">
      <Title>Webhook Settings</Title>
      <Subtitle>View your tenant webhook settings</Subtitle>
      <Card className="mt-2.5">
        <div className="flex justify-between">
          <Icon variant="light" icon={GlobeAltIcon} size="lg" color="orange" />
          <Button
            variant="light"
            icon={PlayIcon}
            color="orange"
            onClick={tryNow}
          >
            Try now
          </Button>
        </div>
        <div className="flex">
          <div className="w-3/5">
            <Title className="mt-6">URL: {data?.webhookApi}</Title>
            <Subtitle className="mt-2">API Key: {data?.apiKey}</Subtitle>
          </div>
          <CopyBlock {...copyBlockProps} />
        </div>
      </Card>
    </div>
  );
}
