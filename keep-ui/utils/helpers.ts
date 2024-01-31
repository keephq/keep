import { toast } from "react-toastify";
import { getApiURL } from "./apiUrl";
import { Provider } from "../app/providers/providers";
import moment from "moment";

export function onlyUnique(value: string, index: number, array: string[]) {
  return array.indexOf(value) === index;
}

function isValidDate(d: Date) {
  return d instanceof Date && !isNaN(d.getTime());
}

export function toDateObjectWithFallback(date: string | Date) {
  /**
   * Since we have a weak typing validation in the backend today (lastReceived is just a string),
   * we need to make sure that we have a valid date object before we can use it.
   *
   * Having invalid dates from the backend will cause the frontend to crash.
   * (new Date(invalidDate) throws an exception)
   */
  if (date instanceof Date) {
    return date;
  }

  // If the date is not a valid date, it will return a date object with the given date string
  // https://stackoverflow.com/questions/1353684/detecting-an-invalid-date-date-instance-in-javascript
  const dateObject = new Date(date);
  if (isValidDate(dateObject)) {
    return dateObject;
  }
  // If the date is not a valid date, return a date object with the current date time
  return new Date();
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

export function getAlertLastReceieved(lastRecievedFromAlert: Date) {
  let lastReceived = "unknown";
  if (lastRecievedFromAlert) {
    lastReceived = lastRecievedFromAlert.toString();
    try {
      lastReceived = moment(lastRecievedFromAlert).fromNow();
    } catch {}
  }
  return lastReceived;
}
