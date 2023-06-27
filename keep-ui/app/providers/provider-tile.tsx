import { Text } from "@tremor/react";
import { Provider } from "./providers";
import Image from "next/image";

interface Props {
  provider: Provider;
  onClick: () => void;
}

export default function ProviderTile({ provider, onClick }: Props) {
  return (
    <div className="flex flex-col justify-around items-center bg-white rounded-md shadow-md w-44 h-44 m-5" onClick={onClick}>
      <div>{provider.installed ? <>Installed</> : null}</div>
      <Image
        src={`/icons/${provider.type}-icon.png`}
        width={60}
        height={60}
        alt={provider.type}
      />
      <Text className="capitalize">{provider.type}</Text>
    </div>
  );
}
