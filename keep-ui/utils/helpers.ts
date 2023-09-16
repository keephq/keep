import { toast } from "react-toastify";
import { getApiURL } from "./apiUrl";
import { Provider } from "../app/providers/providers";

export function onlyUnique(value: string, index: number, array: string[]) {
  return array.indexOf(value) === index;
}

export async function installWebhook(provider: Provider, accessToken: string) {
  toast.promise(
    fetch(
      `${getApiURL()}/providers/install/webhook/${provider.type}/${
        provider.id
      }`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${accessToken}`,
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
