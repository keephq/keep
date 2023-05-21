// @ts-nocheck
'use client';
import React, { useState, useEffect } from 'react';
import { Table } from '@tremor/react';
import ProviderRow from './provider-row';
import {Provider} from './provider-row';
import { SessionProvider } from 'next-auth/react';
import Providers from './providers';

type ProvidersTableProps = {
  providers: Provider[];
};

// This runs on the client
const ProvidersTable = ({session, installed_providers}) => {
  const [expandedProviderId, setExpandedProviderId] = useState<string | null>(null);

  const handleExpand = (providerId: string) => {
    setExpandedProviderId((prevState) => (prevState === providerId ? null : providerId));
  };

  const updatedProviders = Providers.map((provider) => {
  const installedProvider = installed_providers.find((installedProvider) => installedProvider.name === provider.id);
  const connected = !!installedProvider;

  // Update authentication values based on the name
  const authentication = provider.authentication.map((method) => {
    const { name } = method;

    if (connected && installedProvider.details.authentication[name]) {
      return {
        ...method,
        value: installedProvider.details.authentication[name],
      };
    }

    return method;
  });

  return {
    ...provider,
    connected,
    authentication,
  };
});


  return (
    <SessionProvider session={session}>
      <Table>
        <tbody>
          {updatedProviders.map((provider) => (
            <ProviderRow
              key={provider.id}
              provider={provider}
              expanded={expandedProviderId === provider.id}
              onExpand={handleExpand}
            />
          ))}
        </tbody>
      </Table>
    </SessionProvider>
  );
};

export default ProvidersTable;
