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

interface SSOProvider {
  id: string;
  name: string;
  connected: boolean;
}

const SSOSettings = () => {
  const api = useApi();
  const { data, error } = useSWR<{
    sso: boolean;
    providers: SSOProvider[];
    wizardUrl: string;
  }>(`/settings/sso`, (url: string) => api.get(url));

  if (!data) return <Loading />;
  if (error) return <div>Error loading SSO settings: {error.message}</div>;

  const { sso: supportsSSO, providers, wizardUrl } = data;

  return (
    <div className="h-full flex flex-col">
      <Title>SSO Settings</Title>
      {supportsSSO && providers.length > 0 && (
        <Card className="mt-4 p-4">
          <Table>
            <TableHead>
              <TableRow>
                <TableHeaderCell>Provider</TableHeaderCell>
                <TableHeaderCell>Status</TableHeaderCell>
                <TableHeaderCell>Actions</TableHeaderCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {providers.map((provider) => (
                <TableRow key={provider.id}>
                  <TableCell>{provider.name}</TableCell>
                  <TableCell>
                    {provider.connected ? "Connected" : "Not connected"}
                  </TableCell>
                  <TableCell>
                    <Button
                      style={{ marginRight: "10px" }}
                      onClick={() => {
                        /* Connect logic here */
                      }}
                    >
                      Connect
                    </Button>
                    <Button
                      color="orange"
                      onClick={() => {
                        /* Disconnect logic here */
                      }}
                    >
                      Disconnect
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
