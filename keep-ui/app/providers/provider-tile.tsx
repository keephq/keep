import { Button, Icon, Subtitle, Text } from "@tremor/react";
import { Provider } from "./providers";
import Image from "next/image";
import { Bars3Icon } from "@heroicons/react/20/solid";
import { useSession } from "../../utils/customAuth";
import { getApiURL } from "../../utils/apiUrl";

interface Props {
  provider: Provider;
  onClick: () => void;
  onDelete?: (provider: Provider) => void;
}

function InstalledSection() {
  return (
    <div className="flex w-full items-center justify-between">
      <Text color="green" className="ml-2.5 text-xs">
        Connected
      </Text>
      {/* <Icon
        size="xs"
        icon={Bars3Icon}
        className="mr-2.5 hover:bg-gray-100"
        color="gray"
      /> */}
    </div>
  );
}

export default function ProviderTile({ provider, onClick, onDelete }: Props) {
  const { data: session, status, update } = useSession();

  async function deleteProvider() {
    if (confirm("Are you sure you want to delete this provider?")) {
      const response = await fetch(
        `${getApiURL()}/providers/${provider.type}/${provider.id}`,
        {
          method: "DELETE",
          headers: {
            Authorization: `Bearer ${session?.accessToken!}`,
          },
        }
      );
      if (response.ok) {
        onDelete!(provider);
      } else {
        alert("Failed to delete provider");
      }
    }
  }

  return (
    <div
      className={`group flex flex-col justify-around items-center bg-white rounded-md shadow-md w-44 h-44 m-2.5 hover:shadow-xl ${
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
      <div className="h-8">
        <Text
          className={`truncate capitalize group-hover:hidden ${
            provider.installed && provider.details?.name ? "w-[100px]" : ""
          }`}
          title={provider.installed ? provider.details.name : ""}
        >
          {provider.type}{" "}
          {provider.details.name && `(${provider.details.name})`}
        </Text>
        {!provider.installed && (
          <Button
            variant="secondary"
            size="xs"
            color="green"
            className="hidden group-hover:block"
          >
            Connect
          </Button>
        )}
        {provider.installed && (
          <Button
            variant="secondary"
            size="xs"
            color="red"
            className="hidden group-hover:block"
            onClick={deleteProvider}
          >
            Delete
          </Button>
        )}
      </div>
    </div>
  );
}
