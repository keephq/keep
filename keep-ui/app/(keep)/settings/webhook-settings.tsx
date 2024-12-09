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
  Callout,
} from "@tremor/react";
import Loading from "@/app/(keep)/loading";
import { useRouter } from "next/navigation";
import { CodeBlock, a11yLight } from "react-code-blocks";
import useSWR from "swr";
import { toast } from "react-toastify";
import { v4 as uuidv4 } from "uuid";
import { ExclamationCircleIcon } from "@heroicons/react/24/outline";
import * as Frigade from "@frigade/react";
import { useApi } from "@/shared/lib/hooks/useApi";

interface Webhook {
  webhookApi: string;
  apiKey: string;
  modelSchema: any;
}

interface Props {
  selectedTab: string;
}

export default function WebhookSettings({ selectedTab }: Props) {
  const [codeTabIndex, setCodeTabIndex] = useState<number>(0);

  const api = useApi();

  const { data, error, isLoading } = useSWR<Webhook>(
    api.isReady() && selectedTab === "webhook" ? `/settings/webhook` : null,
    (url) => api.get(url),
    { revalidateOnFocus: false }
  );
  const router = useRouter();

  if (error)
    return (
      <Callout
        className="mt-4"
        title="Error"
        icon={ExclamationCircleIcon}
        color="rose"
      >
        Failed to load webhook settings.
        <br></br>
        <br></br>
        {error.message}
      </Callout>
    );

  if (!data || isLoading) return <Loading />;

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
      code: `import requests

response = requests.post("${data.webhookApi}",
headers={
  "Content-Type": "application/json",
  "Accept": "application/json",
  "X-API-KEY": "${data.apiKey}"
},
data="""${exampleJson}""")
      `,
    },
    {
      title: "Node",
      language: "javascript",
      code: `const https = require('https');
const { URL } = require('url');

const url = new URL('${data.webhookApi}');
const data = JSON.stringify(${exampleJson});

const options = {
  hostname: url.hostname,
  port: 443,
  path: url.pathname,
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
      router.push("/alerts/feed");
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
              <Button
                icon={PlayIcon}
                color="orange"
                onClick={tryNow}
                id="tooltip-select-0"
              >
                Click to create an example Alert
              </Button>
              <Frigade.Tour flowId="flow_4iLdns11" />
            </div>
          </div>
          <TabGroup
            className="flex-1 min-w-0 pl-2"
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
