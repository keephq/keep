import React from 'react';
import useSWR from 'swr';
import { Card, Title, Subtitle, Table, TableBody, TableCell, TableHead, TableHeaderCell, TableRow, Button, Icon } from '@tremor/react';
import { fetcher } from 'utils/fetcher';
import { getApiURL } from 'utils/apiUrl';
import Loading from 'app/loading';
import Image from "next/image";

interface SSOProvider {
  id: string;
  name: string;
  connected: boolean;
}

interface Props {
  accessToken: string;
}

const SSOSettings: React.FC<Props> = ({ accessToken }) => {
  const apiUrl = getApiURL();
  const { data, error } = useSWR<{ sso: boolean, providers: SSOProvider[], wizardUrl: string }>(
    `${apiUrl}/settings/sso`,
    url => fetcher(url, accessToken)
  );

  if (!data) return <Loading />;
  if (error) return <div>Error loading SSO settings: {error.message}</div>;

  const { sso: supportsSSO, providers, wizardUrl } = data;

  const handleConnectSSO = () => {
    if (supportsSSO && wizardUrl) {
      window.open(wizardUrl, '_blank');
    }
  };

  const emptyStateContent = (
    <div className="flex flex-col items-center justify-center space-y-4">
      {supportsSSO && (
        <div className="flex space-x-4">
          <Image
            src={`/icons/auth0-icon.png`}
            width={48}
            height={48}
            alt="auth0"
          />
          <Image
            src={`/icons/okta-icon.png`}
            width={80}
            height={80}
            alt="Okta"
          />
        </div>
      )}
      <Button color="orange" onClick={handleConnectSSO} disabled={!supportsSSO}>
        Connect a SSO Provider
      </Button>
    </div>
  );

  return (
    <div className="p-6">
      <Title>SSO Settings</Title>
      <Card className="mt-4 p-4">
        {supportsSSO ? (
          providers.length > 0 ? (
            <Table>
              <TableHead>
                <TableRow>
                  <TableHeaderCell>Provider</TableHeaderCell>
                  <TableHeaderCell>Status</TableHeaderCell>
                  <TableHeaderCell>Actions</TableHeaderCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {providers.map(provider => (
                  <TableRow key={provider.id}>
                    <TableCell>{provider.name}</TableCell>
                    <TableCell>{provider.connected ? "Connected" : "Not connected"}</TableCell>
                    <TableCell>
                      <Button style={{ marginRight: "10px" }} onClick={() => {/* Connect logic here */}}>
                        Connect
                      </Button>
                      <Button color="orange" onClick={() => {/* Disconnect logic here */}}>
                        Disconnect
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : emptyStateContent
        ) : emptyStateContent}
      </Card>
    </div>
  );
};

export default SSOSettings;
