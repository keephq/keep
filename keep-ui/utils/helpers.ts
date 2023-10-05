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
    ).then((res) => {
      return res.json().then((data) => {
        if (!res.ok) {
          return Promise.reject(data);
        }
      });
    }),
    {
      pending: "Webhook installing 🤞",
      success: `${provider.type} webhook installed 👌`,
      error: {
        render({ data }) {
          console.log(data);
          // When the promise reject, data will contains the error
          return `Webhook installation failed 😢 Error: ${
            (data as any).detail
          }`;
        },
      },
    },
    {
      position: toast.POSITION.TOP_LEFT,
    }
  );
}
