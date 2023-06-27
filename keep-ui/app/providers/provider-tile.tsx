import { Button, Icon, Text } from "@tremor/react";
import { Provider } from "./providers";
import Image from "next/image";
import { Bars3Icon } from "@heroicons/react/20/solid";

interface Props {
  provider: Provider;
  onClick: () => void;
}

function InstalledSection() {
  return (
    <div className="flex w-full items-center justify-between">
      <Text color="green" className="ml-2.5 text-xs">
        Connected
      </Text>
      <Icon
        size="xs"
        icon={Bars3Icon}
        className="mr-2.5 hover:bg-gray-100"
        color="gray"
      />
    </div>
  );
}

export default function ProviderTile({ provider, onClick }: Props) {
  return (
    <div
      className={`group flex flex-col justify-around items-center bg-white rounded-md shadow-md w-44 h-44 m-2.5 hover:border-solid hover:border-2 ${
        provider.installed ? "grayscale-0" : "grayscale"
      } hover:grayscale-0`}
      onClick={onClick}
    >
      {provider.installed ? InstalledSection() : <div></div>}
      <Image
        src={`/icons/${provider.type}-icon.png`}
        width={60}
        height={60}
        alt={provider.type}
      />
      <Text className="capitalize group-hover:hidden">
        {provider.type}
      </Text>
      <Button
        variant="secondary"
        size="xs"
        color="green"
        className="hidden group-hover:block"
      >
        Connect
      </Button>
    </div>
  );
}
