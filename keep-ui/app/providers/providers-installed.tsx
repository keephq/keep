"use client";
import { Text } from "@tremor/react";
import { Provider } from "./providers";
import ProviderTile from "./provider-tile";

interface Props {
  providers: Provider[];
}

export default function ProvidersInstalled({ providers }: Props) {
  return (
    <div>
      <Text className="ml-5">Installed Providers</Text>
      {providers.map((provider) => (
        <ProviderTile
          key={provider.id}
          provider={provider}
          onClick={() => {}}
        />
      ))}
    </div>
  );
}
