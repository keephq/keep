"use client";
import React from "react";
import { Table } from "@tremor/react";
import ProviderRow from "./provider-row";
import { SessionProvider } from "next-auth/react";
import { Session } from "next-auth";
import { Providers } from "./providers";

const isSingleTenant = process.env.NEXT_PUBLIC_AUTH_ENABLED === "false";

export default function ProvidersTable({
  session,
  providers,
}: {
  session: Session | null;
  providers: Providers;
}) {
  // update the providers
  Object.keys(providers).map((providerName) => {
    const provider = providers[providerName];
    // Update authentication values based on the name
    if (provider.details) {
      Object.keys(provider.details.authentication).map((authKey) => {
        provider.config[authKey].value =
          provider.details.authentication[authKey];
      });
    }
  });
  return (
    <Table>
      <tbody>
        {Object.entries(providers)
          .filter(
            ([providerKey, provider]) => Object.keys(provider.config).length > 0
          )
          .map(([providerKey, provider]) => (
            <ProviderRow key={providerKey} provider={provider} />
          ))}
      </tbody>
    </Table>
  );
}
