import {
  Badge,
  Button,
  Card,
  Subtitle,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
  Text,
  Title,
} from "@tremor/react";
import Loading from "@/app/(keep)/loading";
import { a11yLight, CopyBlock } from "react-code-blocks";
import useSWR, { mutate } from "swr";
import { KeyIcon, TrashIcon } from "@heroicons/react/24/outline";
import { useState } from "react";
import { AuthType } from "utils/authenticationType";
import CreateApiKeyModal from "../create-api-key-modal";
import { useRoles } from "utils/hooks/useRoles";
import { UpdateIcon } from "@radix-ui/react-icons";
import { useApi } from "@/shared/lib/hooks/useApi";
import { useConfig } from "@/utils/hooks/useConfig";
import { PageSubtitle, PageTitle, showErrorToast } from "@/shared/ui";
import { ApiKey } from "@/app/(keep)/settings/auth/types";

interface Props {
  selectedTab: string;
}

interface ApiKeyResponse {
  apiKeys: ApiKey[];
}

export default function ApiKeySettings({ selectedTab }: Props) {
  const { data: configData } = useConfig();
  const api = useApi();
  const { data, error, isLoading } = useSWR<ApiKeyResponse>(
    selectedTab === "api-key" ? "/settings/apikeys" : null,
    async (url) => {
      const response = await api.get(url);
      setApiKeys(response.apiKeys);
      return response;
    },
    { revalidateOnFocus: false }
  );

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

  const authType = configData?.AUTH_TYPE as AuthType;
  const createApiKeyEnabled = authType !== AuthType.NOAUTH;

  const handleRegenerate = async (
    apiKeyId: string,
    event: React.MouseEvent
  ) => {
    event.stopPropagation();
    const confirmed = confirm(
      "This action cannot be undone. This will revoke the key and generate a new one. Any further requests made with this key will fail. Make sure to update any applications that use this key."
    );

    if (confirmed) {
      try {
        const res = await api.put(`/settings/apikey`, { apiKeyId });
        mutate(`/settings/apikeys`);
      } catch (error) {
        showErrorToast(error, "Failed to regenerate API key");
      }
    }
  };

  const handleDelete = async (apiKeyId: string, event: React.MouseEvent) => {
    event.stopPropagation();
    const confirmed = confirm(
      "This action cannot be undone. This will permanently delete the API key and any future requests using this key will fail."
    );

    if (confirmed) {
      try {
        const res = await api.delete(`/settings/apikey/${apiKeyId}`);
        mutate(`/settings/apikeys`);
      } catch (error) {
        showErrorToast(error, "Failed to delete API key");
      }
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <header className="flex justify-between">
        <div className="flex flex-col">
          <PageTitle>API Keys</PageTitle>
          <PageSubtitle>Manage your tenant API keys</PageSubtitle>
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
      </header>
      <Card className="p-0">
        {apiKeys.length ? (
          <Table>
            <TableHead>
              <TableRow className="border-b border-tremor-border dark:border-dark-tremor-border">
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
        setApiKeys={setApiKeys}
        roles={roles}
      />
    </div>
  );
}
