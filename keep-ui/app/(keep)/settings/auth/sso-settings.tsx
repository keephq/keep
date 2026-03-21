import React from "react";
import useSWR from "swr";
import {
  Card,
  Title,
  Subtitle,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
  Button,
} from "@tremor/react";
import Loading from "@/app/(keep)/loading";
import { useApi } from "@/shared/lib/hooks/useApi";
import { useI18n } from "@/i18n/hooks/useI18n";

interface SSOProvider {
  id: string;
  name: string;
  connected: boolean;
}

const SSOSettings = () => {
  const { t } = useI18n();
  const api = useApi();
  const { data, error } = useSWR<{
    sso: boolean;
    providers: SSOProvider[];
    wizardUrl: string;
  }>(`/settings/sso`, (url: string) => api.get(url));

  if (!data) return <Loading />;
  if (error) return <div>{t("errors.message")}: {error.message}</div>;

  const { sso: supportsSSO, providers, wizardUrl } = data;

  return (
    <div className="h-full flex flex-col">
      <Title>{t("settings.sso.title")}</Title>
      {supportsSSO && providers.length > 0 && (
        <Card className="mt-4 p-4">
          <Table>
            <TableHead>
              <TableRow>
                <TableHeaderCell>{t("settings.sso.labels.provider")}</TableHeaderCell>
                <TableHeaderCell>{t("common.labels.status")}</TableHeaderCell>
                <TableHeaderCell>{t("common.actions.actions")}</TableHeaderCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {providers.map((provider) => (
                <TableRow key={provider.id}>
                  <TableCell>{provider.name}</TableCell>
                  <TableCell>
                    {provider.connected ? t("providers.connected") : t("providers.notConnected")}
                  </TableCell>
                  <TableCell>
                    <Button
                      style={{ marginRight: "10px" }}
                      onClick={() => {
                        /* Connect logic here */
                      }}
                    >
                      {t("common.actions.connect")}
                    </Button>
                    <Button
                      color="orange"
                      onClick={() => {
                        /* Disconnect logic here */
                      }}
                    >
                      {t("common.actions.disconnect")}
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}
      {wizardUrl && (
        <Card className="mt-4 p-4 flex-grow flex flex-col">
          <iframe src={wizardUrl} className="w-full flex-grow border-none" />
        </Card>
      )}
    </div>
  );
};

export default SSOSettings;
