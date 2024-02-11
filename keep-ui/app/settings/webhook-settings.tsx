"use client";

import { useState } from "react";
import { PlayIcon, ClipboardDocumentIcon } from "@heroicons/react/24/outline";
import {
  Button,
  Card,
  Subtitle,
  TabGroup,
  TabList,
  Tab,
  Title,
  TabPanels,
  TabPanel,
} from "@tremor/react";
import Loading from "app/loading";
import { useRouter } from "next/navigation";
import { CodeBlock, a11yLight } from "react-code-blocks";
import useSWR from "swr";
import { getApiURL } from "utils/apiUrl";
import { fetcher } from "utils/fetcher";
import { toast } from "react-toastify";
import { v4 as uuidv4 } from "uuid";

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
  const [codeTabIndex, setCodeTabIndex] = useState<number>(0);

  const apiUrl = getApiURL();

  const { data, error, isLoading } = useSWR<Webhook>(
    selectedTab === "webhook" ? `${apiUrl}/settings/webhook` : null,
    (url) => fetcher(url, accessToken),
    { revalidateOnFocus: false }
  );
  const router = useRouter();

  if (!data || isLoading) return <Loading />;
  if (error) return <div>{error.message}</div>;

  const [example] = data.modelSchema.examples;

  const exampleJson = JSON.stringify(
    {
      ...example,
      lastReceived: new Date().toISOString(),
      id: uuidv4(),
      fingerprint: uuidv4(),
    },
    null,
    2
  );

  const code = `curl --location '${data.webhookApi}' \\
  --header 'Content-Type: application/json' \\
  --header 'Accept: application/json' \\
  --header 'X-API-KEY: ${data.apiKey}' \\
  --data '${exampleJson}'`;

  const languages = [
    { title: "Bash", language: "shell", code: code },
    {
      title: "Python",
      language: "python",
      code: `
import requests

response = requests.post("https://api.keephq.dev/alerts/event",
headers={
  "Content-Type": "application/json",
  "Accept": "application/json",
  "X-API-KEY": "${data.apiKey}"
},
json=${exampleJson})
      `,
    },
    {
      title: "Node",
      language: "javascript",
      code: `
const https = require('https');

const data = JSON.stringify(${exampleJson});

const options = {
  hostname: 'api.keephq.dev',
  port: 443,
  path: '/alerts/event',
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
    'X-API-KEY': '${data.apiKey}',
    'Content-Length': data.length
  }
};

const req = https.request(options, (res) => {
  console.log(\`statusCode: $\{res.statusCode}\`);

  res.on('data', (d) => {
    process.stdout.write(d);
  });
});

req.on('error', (error) => {
  console.error(error);
});

req.write(data);
req.end();
    `,
    },
  ] as const;

  const tryNow = async () => {
    const requestOptions: RequestInit = {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        "X-API-KEY": data.apiKey,
      },
      body: exampleJson,
    };

    const resp = await fetch(data.webhookApi, requestOptions);
    if (resp.ok) {
      router.push("/alerts");
    } else {
      alert("Something went wrong! Please try again.");
    }
  };

  const onCopyCode = () => {
    const currentCode = languages.at(codeTabIndex);

    if (currentCode !== undefined) {
      return window.navigator.clipboard.writeText(currentCode.code).then(() =>
        toast("Code copied to clipboard!", {
          position: "top-left",
          type: "success",
        })
      );
    }
  };

  return (
    <div className="mt-10">
      <Title>Webhook Settings</Title>
      <Subtitle>View your tenant webhook settings</Subtitle>
      <Card className="mt-2.5">
        <div className="flex divide-x">
          <div className="flex-1 pr-2 flex flex-col gap-y-2">
            <Title>URL: {data.webhookApi}</Title>
            <Subtitle>API Key: {data.apiKey}</Subtitle>
            <div>
              <Button icon={PlayIcon} color="orange" onClick={tryNow}>
                Click to create an example Alert
              </Button>
            </div>
          </div>
          <TabGroup
            className="flex-1 pl-2"
            index={codeTabIndex}
            onIndexChange={setCodeTabIndex}
          >
            <div className="flex justify-between items-center">
              <TabList variant="solid" color="orange">
                {languages.map(({ title }) => (
                  <Tab key={title}>{title}</Tab>
                ))}
              </TabList>
              <Button
                icon={ClipboardDocumentIcon}
                size="xs"
                color="orange"
                onClick={onCopyCode}
              >
                Copy code
              </Button>
            </div>
            <TabPanels>
              {languages.map(({ title, language, code }) => (
                <TabPanel key={title}>
                  <CodeBlock
                    language={language}
                    theme={a11yLight}
                    // @ts-ignore - `text` isn't a valid prop, but it appears in the docs
                    text={code}
                    customStyle={{ overflowY: "scroll" }}
                    showLineNumbers={false}
                  />
                </TabPanel>
              ))}
            </TabPanels>
          </TabGroup>
        </div>
      </Card>
    </div>
  );
}
