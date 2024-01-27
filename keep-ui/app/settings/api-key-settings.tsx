"use client";

import { Card, Title, Subtitle, Button} from "@tremor/react";
import Loading from "app/loading";
import { CopyBlock, a11yLight } from "react-code-blocks";
import useSWR from "swr";
import { getApiURL } from "utils/apiUrl";
import { KeyIcon } from "@heroicons/react/24/outline";
import { fetcher } from "utils/fetcher";
import { useState } from 'react';
import { AuthenticationType } from "utils/authenticationType";
import { Config } from "./users-settings";
import CreateApiKeyModal from "./create-api-key-modal";

interface ApiKeyResponse {
  apiKey: string;
}

interface Props {
  accessToken: string;
  selectedTab: string;
}

export default function ApiKeySettings({ accessToken, selectedTab }: Props) {
  const apiUrl = getApiURL();
  const { data, error, isLoading } = useSWR<ApiKeyResponse>(
    selectedTab === "api-key" ? `${apiUrl}/settings/apikeys` : null,
    async (url) => {
        const response = await fetcher(url, accessToken);
        setApiKeys(response.apiKeys);
        return response;
    },
    { revalidateOnFocus: false }
  );


  const { data: configData } = useSWR<Config>("/api/config", fetcher, {
    revalidateOnFocus: false,
  });


  const [isApiKeyModalOpen, setApiKeyModalOpen] = useState(false);
  const [apiKeys, setApiKeys] = useState([]);

  if (isLoading) return <Loading />;
  if (error) return <div>{error.message}</div>;

  const copyBlockApiKeyProps = {
    theme: { ...a11yLight },
    language: "text",
    text: apiKeys.length ? apiKeys[0].key_hash : "You have no active API Keys.",
    codeBlock: true,
    showLineNumbers: false,
  };

  // Determine runtime configuration
  const authType = configData?.AUTH_TYPE as AuthenticationType;
  // Create API key disabled if authType is none
  const createApiKeyEnabled = authType !== AuthenticationType.NO_AUTH

  return (
    <div className="mt-10">
      <div className="flex justify-between">
        <div className="flex flex-col">
          <Title>API Keys</Title>
          <Subtitle>Add, edit or deactivate API keys from your tenant</Subtitle>
        </div>

        <div>
          <Button
            color="orange"
            size="md"
            icon={KeyIcon}
            onClick={() => setApiKeyModalOpen(true)}
            disabled={!createApiKeyEnabled}
            tooltip={!createApiKeyEnabled ? "API Key creation is disabled because Keep is running in NO_AUTH mode.": "Add user"}
          >
            Create API key 
          </Button>
        </div>
      </div>
      <Card className="mt-2.5">
        {/* Ensure CopyBlock is the only element within the card for proper spacing */}
        <CopyBlock {...copyBlockApiKeyProps} />
      </Card>
      <CreateApiKeyModal
        isOpen={isApiKeyModalOpen}
        onClose={() => setApiKeyModalOpen(false)}
        authType={authType}
        accessToken={accessToken}
        setApiKeys={setApiKeys}
        apiUrl={apiUrl}
      />
    </div>
  );
}
