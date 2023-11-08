"use client";

import { Card, Title } from "@tremor/react";
import Loading from "app/loading";
import { CopyBlock, a11yLight } from "react-code-blocks";
import useSWR from "swr";
import { getApiURL } from "utils/apiUrl";
import { fetcher } from "utils/fetcher";

interface ApiKeyResponse {
  apiKey: string;
}

interface Props {
  accessToken: string;
}

export default function ApiKeySettings({ accessToken }: Props) {
  const apiUrl = getApiURL();
  const { data, error, isLoading } = useSWR<ApiKeyResponse>(
    `${apiUrl}/settings/apikey`,
    (url) => fetcher(url, accessToken)
  );

  if (isLoading) return <Loading />;
  if (error) return <div>{error.message}</div>;

  const copyBlockProps = {
    theme: { ...a11yLight },
    language: "text",
    text: data?.apiKey || '',
    codeBlock: true,
    showLineNumbers: false,
  };

  return (
    <div className="mt-10">
      <Title>API Key</Title>
      <Card className="mt-2.5">
        {/* Ensure CopyBlock is the only element within the card for proper spacing */}
        <CopyBlock {...copyBlockProps} />
      </Card>
    </div>
  );
}
