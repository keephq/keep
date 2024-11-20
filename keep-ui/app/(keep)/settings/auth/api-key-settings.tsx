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
  Text,
  Badge,
} from "@tremor/react";
import Loading from "app/loading";
import { CopyBlock, a11yLight } from "react-code-blocks";
import useSWR from "swr";
import { useApiUrl } from "utils/hooks/useConfig";
import { KeyIcon, TrashIcon } from "@heroicons/react/24/outline";
import { fetcher } from "utils/fetcher";
import { useState } from "react";
import { AuthenticationType } from "utils/authenticationType";
import CreateApiKeyModal from "../create-api-key-modal";
import { useRoles } from "utils/hooks/useRoles";
import { getSession } from "next-auth/react";
import { mutate } from "swr";
import { UpdateIcon } from "@radix-ui/react-icons";

interface Props {
  accessToken: string;
  selectedTab: string;
}

export interface ApiKey {
  reference_id: string;
  secret: string;
  created_by: string;
  created_at: string;
  last_used?: string;
  role?: string;
}

interface ApiKeyResponse {
  apiKeys: ApiKey[];
}

interface Config {
  AUTH_TYPE: string;
}

export default function ApiKeySettings({ accessToken, selectedTab }: Props) {
  const apiUrl = useApiUrl();
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

  const { data: roles = [] } = useRoles();

  const [isApiKeyModalOpen, setApiKeyModalOpen] = useState(false);
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);

  if (isLoading) return <Loading />;
  if (error) return <div>{error.message}</div>;

  const getCopyBlockProps = (secret: string) => ({
    theme: { ...a11yLight },
    language: "text",
    text: secret,
    codeBlock: true,
    showLineNumbers: false,
  });

  const authType = configData?.AUTH_TYPE as AuthenticationType;
  const createApiKeyEnabled = authType !== AuthenticationType.NOAUTH;

  const handleRegenerate = async (
    apiKeyId: string,
    event: React.MouseEvent
  ) => {
    event.stopPropagation();
    const confirmed = confirm(
      "This action cannot be undone. This will revoke the key and generate a new one. Any further requests made with this key will fail. Make sure to update any applications that use this key."
    );

    if (confirmed) {
      const session = await getSession();
      const res = await fetch(`${apiUrl}/settings/apikey`, {
        method: "PUT",
        headers: {
          Authorization: `Bearer ${session!.accessToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ apiKeyId: apiKeyId }),
      });
      if (res.ok) {
        mutate(`${apiUrl}/settings/apikeys`);
      } else {
        alert("Something went wrong! Please try again.");
      }
    }
  };

  const handleDelete = async (apiKeyId: string, event: React.MouseEvent) => {
    event.stopPropagation();
    const confirmed = confirm(
      "This action cannot be undone. This will permanently delete the API key and any future requests using this key will fail."
    );

    if (confirmed) {
      const session = await getSession();
      const res = await fetch(`${apiUrl}/settings/apikey/${apiKeyId}`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${session!.accessToken}`,
        },
      });
      if (res.ok) {
        mutate(`${apiUrl}/settings/apikeys`);
      } else {
        alert("Something went wrong! Please try again.");
      }
    }
  };

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
            tooltip={
              !createApiKeyEnabled
                ? "API Key creation is disabled because Keep is running in NO_AUTH mode."
                : "Add user"
            }
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
                <TableHeaderCell className="text-left w-1/4">
                  Key
                </TableHeaderCell>
                <TableHeaderCell className="text-left">Role</TableHeaderCell>
                <TableHeaderCell className="text-left">
                  Created By
                </TableHeaderCell>
                <TableHeaderCell className="text-left">
                  Created At
                </TableHeaderCell>
                <TableHeaderCell className="text-left">
                  Last Used
                </TableHeaderCell>
                <TableHeaderCell className="w-1/12"></TableHeaderCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {apiKeys.map((key) => (
                <TableRow
                  key={key.reference_id}
                  className="hover:bg-gray-50 transition-colors duration-200 cursor-pointer group"
                >
                  <TableCell>{key.reference_id}</TableCell>
                  <TableCell className="text-left">
                    <CopyBlock {...getCopyBlockProps(key.secret)} />
                  </TableCell>
                  <TableCell className="text-left">
                    <Badge color="orange">{key.role || "N/A"}</Badge>
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
                  <TableCell className="w-1/12">
                    <div className="flex justify-end space-x-2 opacity-0 group-hover:opacity-100 transition-opacity">
                      <Button
                        tooltip="Regenerate key"
                        icon={UpdateIcon}
                        variant="light"
                        color="orange"
                        onClick={(e) => handleRegenerate(key.reference_id, e)}
                      />
                      <Button
                        tooltip="Delete key"
                        icon={TrashIcon}
                        variant="light"
                        color="orange"
                        onClick={(e) => handleDelete(key.reference_id, e)}
                      />
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ) : (
          <div> There are no active API keys </div>
        )}
      </Card>
      <CreateApiKeyModal
        isOpen={isApiKeyModalOpen}
        onClose={() => setApiKeyModalOpen(false)}
        accessToken={accessToken}
        setApiKeys={setApiKeys}
        apiUrl={apiUrl!}
        roles={roles}
      />
    </div>
  );
}
