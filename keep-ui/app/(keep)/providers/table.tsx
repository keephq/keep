import React from "react";
import { Table } from "@tremor/react";
import ProviderRow from "./provider-row";
import { Providers } from "./providers";

export default function ProvidersTable({
  providers,
}: {
  providers: Providers;
}) {
  return (
    <Table>
      <tbody>
        {providers
          .filter((provider) => Object.keys(provider.details).length > 0)
          .map((provider) => (
            <ProviderRow key={provider.id} provider={provider} />
          ))}
      </tbody>
    </Table>
  );
}
