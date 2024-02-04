"use client";

import {
    Card,
    Title,
    Subtitle,
    Button,
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeaderCell,
    TableRow,
    Text
} from "@tremor/react";
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
import ApiKeysMenu from "./api-key-menu";

interface ApiKeyResponse {
  apiKey: string;
}

interface Props {
  accessToken: string;
  selectedTab: string;
}

export interface ApiKey {
  reference_id: string;
  secret: string;
  created_by: string;
  created_at: string;
  last_used?: string; // Assuming 'last_used' could be optional
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
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);


  if (isLoading) return <Loading />;
  if (error) return <div>{error.message}</div>;

  const getCopyBlockProps = (secret: string) => {
    return {
        theme: { ...a11yLight },
        language: "text",
        text: secret,
        codeBlock: true,
        showLineNumbers: false,
      };
  }

  // Determine runtime configuration
  const authType = configData?.AUTH_TYPE as AuthenticationType;
  // Create API key disabled if authType is none
  const createApiKeyEnabled = authType !== AuthenticationType.NO_AUTH

  return (
    <div className="mt-10">
      <div className="flex justify-between">
        <div className="flex flex-col">
          <Title>API Keys</Title>
          <Subtitle>Manage your tenant API keys</Subtitle>
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
       {apiKeys.length ? (
        <Table>
          <TableHead>
            <TableRow>
              <TableHeaderCell className="text-left">Name</TableHeaderCell>
              <TableHeaderCell className="text-left">Key</TableHeaderCell>
              <TableHeaderCell className="text-left">
                Created By
              </TableHeaderCell>
              <TableHeaderCell className="text-left">
                Created At
              </TableHeaderCell>
              <TableHeaderCell className="text-left">
                Last Used
              </TableHeaderCell>
              <TableHeaderCell>
              {/* Menu */}
              </TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {apiKeys.map((key) => (
              <TableRow
                key={key.reference_id}
              >
                <TableCell>{key.reference_id}</TableCell>
                <TableCell className="text-left">
                  <CopyBlock
                    {...getCopyBlockProps(key.secret)}
                  />
                </TableCell>

                <TableCell className="text-left">
                  <Text>{key.created_by}</Text>
                </TableCell>
                <TableCell className="text-left">
                  <Text>{key.created_at}</Text>
                </TableCell>

                <TableCell className="text-left">
                  <Text>{key.last_used ?? "Never"}</Text>
                </TableCell>
                <TableCell className="text-left">
                    <ApiKeysMenu apiKeyId={key.reference_id}/>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        ) : <div> There are no active api keys </div>}
        {/* Ensure CopyBlock is the only element within the card for proper spacing */}
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
