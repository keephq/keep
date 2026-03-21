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
import useSWR from "swr";
import { v4 as uuidv4 } from "uuid";
import { ExclamationCircleIcon } from "@heroicons/react/24/outline";
import { useApi } from "@/shared/lib/hooks/useApi";
import { useConfig } from "@/utils/hooks/useConfig";
import { PageSubtitle, showErrorToast, showSuccessToast } from "@/shared/ui";
import { PageTitle } from "@/shared/ui";
import { MonacoEditor } from "@/shared/ui";
import { Link } from "@/components/ui/Link";
import { DOCS_CLIPBOARD_COPY_ERROR_PATH } from "@/shared/constants";
import { useI18n } from "@/i18n/hooks/useI18n";

interface Webhook {
  webhookApi: string;
  apiKey: string;
  modelSchema: any;
}

interface Props {
  selectedTab: string;
}

export default function WebhookSettings({ selectedTab }: Props) {
  const { t } = useI18n();
  const [codeTabIndex, setCodeTabIndex] = useState<number>(0);

  const api = useApi();
  const { data: config } = useConfig();

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
        title={t("webhook.loadingError")}
        icon={ExclamationCircleIcon}
        color="rose"
      >
        {t("webhook.loadingFailed")}
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
      showErrorToast(resp, "Something went wrong! Please try again.");
    }
  };

  const onCopyCode = async () => {
    const currentCode = languages.at(codeTabIndex);
    if (currentCode === undefined) {
      return;
    }

    try {
      await navigator.clipboard.writeText(currentCode.code);
      showSuccessToast(t("webhook.copiedToClipboard"));
    } catch (err) {
      showErrorToast(
        err,
        <p>
          {t("webhook.copyFailed")} {t("webhook.copyFailedDescription")}{" "}
          <Link
            target="_blank"
            href={`${config?.KEEP_DOCS_URL}${DOCS_CLIPBOARD_COPY_ERROR_PATH}`}
          >
            {t("webhook.learnMore")}
          </Link>
        </p>
      );
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <header>
        <PageTitle>{t("settings.webhook.title")}</PageTitle>
        <PageSubtitle>{t("webhook.subtitle")}</PageSubtitle>
      </header>
      <Card>
        <div className="flex divide-x">
          <div className="flex-1 basis-4/12 pr-2 flex flex-col gap-y-2">
            <Title>{t("webhook.url")} {data.webhookApi}</Title>
            <Subtitle>{t("webhook.apiKey")} {data.apiKey}</Subtitle>
            <div>
              <Button
                icon={PlayIcon}
                color="orange"
                onClick={tryNow}
                id="tooltip-select-0"
              >
                {t("webhook.createExampleAlert")}
              </Button>
            </div>
          </div>
          <TabGroup
            className="flex-1 basis-8/12 min-w-0 pl-2"
            index={codeTabIndex}
            onIndexChange={setCodeTabIndex}
          >
            <div className="flex justify-between items-center">
              {/* ml-6 to match the editor left padding */}
              <TabList variant="solid" className="ml-6">
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
                {t("webhook.copyCode")}
              </Button>
            </div>
            <TabPanels>
              {languages.map(({ title, language, code }) => (
                <TabPanel key={title}>
                  <div className="h-[calc(100vh-20rem)]">
                    <MonacoEditor
                      value={code}
                      language={language}
                      theme="vs-light"
                      options={{
                        readOnly: true,
                        minimap: { enabled: false },
                        scrollBeyondLastLine: false,
                        fontSize: 12,
                        lineNumbers: "off",
                        folding: true,
                        wordWrap: "on",
                      }}
                    />
                  </div>
                </TabPanel>
              ))}
            </TabPanels>
          </TabGroup>
        </div>
      </Card>
    </div>
  );
}
