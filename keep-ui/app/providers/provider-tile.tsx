import { Button, Icon, Subtitle, Text } from "@tremor/react";
import { Provider } from "./providers";
import Image from "next/image";
import { Bars3Icon } from "@heroicons/react/20/solid";
import { useSession } from "../../utils/customAuth";
import { getApiURL } from "../../utils/apiUrl";
import ProviderMenu from "./provider-menu";
import { toast } from "react-toastify";

interface Props {
  provider: Provider;
  onClick: () => void;
  onDelete?: (provider: Provider) => void;
}

function InstalledSection(
  onDelete?: () => Promise<void>,
  onInstallWebhook?: () => Promise<void>
) {
  return (
    <div className="flex w-full items-center justify-between">
      <Text color="green" className="ml-2.5 text-xs">
        Connected
      </Text>
      <ProviderMenu onDelete={onDelete} onInstallWebhook={onInstallWebhook} />
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
        toast.error(`Failed to delete ${provider.type} 😢`);
      }
    }
  }

  async function installWebhook() {
    toast.promise(
      fetch(
        `${getApiURL()}/providers/install/webhook/${provider.type}/${
          provider.id
        }`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${session?.accessToken!}`,
          },
        }
      ),
      {
        pending: "Webhook installing 🤞",
        success: `${provider.type} webhook installed 👌`,
        error: `Webhook installation failed 😢`,
      },
      {
        position: toast.POSITION.TOP_LEFT,
      }
    );
  }

  return (
    <div
      className={`group flex flex-col justify-around items-center bg-white rounded-md shadow-md w-44 h-44 m-2.5 hover:shadow-xl ${
        provider.installed ? "grayscale-0" : "grayscale"
      } hover:grayscale-0`}
      onClick={onClick}
    >
      {provider.installed ? (
        InstalledSection(deleteProvider, installWebhook)
      ) : (
        <div></div>
      )}
      <Image
        src={`/icons/${provider.type}-icon.png`}
        width={60}
        height={60}
        alt={provider.type}
      />
      <div className="h-8">
        <Text
          className={`truncate capitalize ${
            provider.installed ? "" : "group-hover:hidden"
          } ${provider.details?.name ? "w-[100px]" : ""}`}
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
        {/* {provider.installed && (
          <Button
            variant="secondary"
            size="xs"
            color="red"
            className="hidden group-hover:block"
            onClick={deleteProvider}
          >
            Delete
          </Button>
        )} */}
      </div>
    </div>
  );
}
