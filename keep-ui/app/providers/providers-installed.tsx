"use client";
import { Text } from "@tremor/react";
import { Provider } from "./providers";
import ProviderTile from "./provider-tile";
import "./providers-available.css";

interface Props {
  providers: Provider[];
}

export default function ProvidersInstalled({ providers }: Props) {
  return (
    <div>
      <Text className="ml-2.5 mt-5">Installed Providers</Text>
      <div className="provider-tiles">
        {providers.map((provider) => (
          <ProviderTile
            key={provider.id}
            provider={provider}
            onClick={() => {}}
          />
        ))}
      </div>
    </div>
  );
}
