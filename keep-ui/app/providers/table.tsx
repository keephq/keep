"use client";
import React, { useState } from "react";
import { Table } from "@tremor/react";
import ProviderRow from "./provider-row";
import Providers from "./providers";
import { SessionProvider } from "next-auth/react";
import { Session } from "next-auth";

const isSingleTenant = process.env.NEXT_PUBLIC_AUTH_ENABLED == "false";

interface InstalledProviders {
  name: string;
  details: { authentication: { [key: string]: string } };
}

// This runs on the client
export default function ProvidersTable({
  session,
  installedProviders,
}: {
  session: Session | null;
  installedProviders: InstalledProviders[];
}) {
  const updatedProviders = Providers.map((provider) => {
    const installedProvider = installedProviders.find(
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
            <ProviderRow key={provider.id} provider={provider} />
          ))
        ) : (
          <SessionProvider session={session}>
            {updatedProviders.map((provider) => (
              <ProviderRow
                key={provider.id || Math.random()}
                provider={provider}
              />
            ))}
          </SessionProvider>
        )}
      </tbody>
    </Table>
  );
}
