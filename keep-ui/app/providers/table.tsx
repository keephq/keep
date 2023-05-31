// @ts-nocheck
"use client";
import React, { useState, useEffect } from "react";
import { Table } from "@tremor/react";
import ProviderRow from "./provider-row";
import { Provider } from "./provider-row";
import Providers from "./providers";
import { SessionProvider } from "next-auth/react";

const isSingleTenant = process.env.NEXT_PUBLIC_AUTH_ENABLED == "false";

type ProvidersTableProps = {
  providers: Provider[];
};

// This runs on the client
const ProvidersTable = ({ installed_providers }) => {
  const [expandedProviderId, setExpandedProviderId] = useState<string | null>(
    null
  );

  const handleExpand = (providerId: string) => {
    setExpandedProviderId((prevState) =>
      prevState === providerId ? null : providerId
    );
  };

  const updatedProviders = Providers.map((provider) => {
    const installedProvider = installed_providers.find(
      (installedProvider) => installedProvider.name === provider.id
    );
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
    <Table>
      <tbody>
        {isSingleTenant ? (
          updatedProviders.map((provider) => (
            <ProviderRow
              key={provider.id}
              provider={provider}
              expanded={expandedProviderId === provider.id}
              onExpand={handleExpand}
            />
          ))
        ) : (
          <SessionProvider>
            {updatedProviders.map((provider) => (
              <ProviderRow
                key={provider.id}
                provider={provider}
                expanded={expandedProviderId === provider.id}
                onExpand={handleExpand}
              />
            ))}
          </SessionProvider>
        )}
      </tbody>
    </Table>
  );

};

export default ProvidersTable;
