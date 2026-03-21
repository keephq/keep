import {
  Badge,
  Button,
  Card,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
  Text,
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
import { useI18n } from "@/i18n/hooks/useI18n";

interface Props {
  selectedTab: string;
}

interface ApiKeyResponse {
  apiKeys: ApiKey[];
}

export default function ApiKeySettings({ selectedTab }: Props) {
  const { t } = useI18n();
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
      t("settings.apiKeys.messages.regenerateConfirm")
    );

    if (confirmed) {
      try {
        const res = await api.put(`/settings/apikey`, { apiKeyId });
        mutate(`/settings/apikeys`);
      } catch (error) {
        showErrorToast(error, t("apiKey.settings.regenerateFailed"));
      }
    }
  };

  const handleDelete = async (apiKeyId: string, event: React.MouseEvent) => {
    event.stopPropagation();
    const confirmed = confirm(
      t("apiKey.settings.deleteConfirm")
    );

    if (confirmed) {
      try {
        const res = await api.delete(`/settings/apikey/${apiKeyId}`);
        mutate(`/settings/apikeys`);
      } catch (error) {
        showErrorToast(error, t("apiKey.settings.deleteFailed"));
      }
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <header className="flex justify-between">
        <div className="flex flex-col">
          <PageTitle>{t("settings.apiKeys.title")}</PageTitle>
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
                ? t("settings.apiKeys.messages.creationDisabled")
                : undefined
            }
          >
            {t("settings.apiKeys.addKey")}
          </Button>
        </div>
      </header>
      <Card className="p-0">
        {apiKeys.length ? (
          <Table>
            <TableHead>
              <TableRow className="border-b border-tremor-border dark:border-dark-tremor-border">
                <TableHeaderCell className="text-left">{t("apiKey.settings.name")}</TableHeaderCell>
                <TableHeaderCell className="text-left w-1/4">
                  {t("apiKey.settings.key")}
                </TableHeaderCell>
                <TableHeaderCell className="text-left">{t("apiKey.settings.role")}</TableHeaderCell>
                <TableHeaderCell className="text-left">
                  {t("apiKey.settings.createdBy")}
                </TableHeaderCell>
                <TableHeaderCell className="text-left">
                  {t("apiKey.settings.createdAt")}
                </TableHeaderCell>
                <TableHeaderCell className="text-left">
                  {t("apiKey.settings.lastUsed")}
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
                    <Text>{key.last_used ?? t("apiKey.settings.never")}</Text>
                  </TableCell>
                  <TableCell className="w-1/12">
                    <div className="flex justify-end space-x-2 opacity-0 group-hover:opacity-100 transition-opacity">
                      <Button
                        tooltip={t("apiKey.settings.regenerateTooltip")}
                        icon={UpdateIcon}
                        variant="light"
                        color="orange"
                        onClick={(e) => handleRegenerate(key.reference_id, e)}
                      />
                      <Button
                        tooltip={t("apiKey.settings.deleteTooltip")}
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
          <div className="p-4"> {t("apiKey.settings.noActiveKeys")} </div>
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
