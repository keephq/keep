import { toast } from "react-toastify";
import { Provider } from "@/app/(keep)/providers/providers";
import moment from "moment";
import { twMerge } from "tailwind-merge";
import { clsx, type ClassValue } from "clsx";

export function onlyUnique(value: string, index: number, array: string[]) {
  return array.indexOf(value) === index;
}

function isValidDate(d: Date) {
  return d instanceof Date && !isNaN(d.getTime());
}

export function capitalize(string: string) {
  return string.charAt(0).toUpperCase() + string.slice(1);
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

export function getAlertLastReceieved(lastRecievedFromAlert: Date) {
  return moment(lastRecievedFromAlert).fromNow();
}

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function areSetsEqual<T>(set1: Set<T>, set2: Set<T>): boolean {
  if (set1.size !== set2.size) {
    return false;
  }

  for (const item of set1) {
    if (!set2.has(item)) {
      return false;
    }
  }

  return true;
}
