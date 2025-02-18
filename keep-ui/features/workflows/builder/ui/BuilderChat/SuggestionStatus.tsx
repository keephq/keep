import { CheckCircleIcon } from "@heroicons/react/20/solid";
import {
  ExclamationCircleIcon,
  NoSymbolIcon,
} from "@heroicons/react/24/outline";

export type SuggestionStatus = "complete" | "error" | "declined";
export type SuggestionResult = {
  status: SuggestionStatus;
  message: string;
  error?: any;
};

export const SuggestionStatus = ({
  status,
  message,
}: {
  status: SuggestionStatus;
  message: string;
}) => {
  if (status === "complete") {
    return (
      <p className="text-sm text-gray-500 flex items-center gap-1">
        <CheckCircleIcon className="w-4 h-4" />
        {message}
      </p>
    );
  }
  if (status === "error") {
    return (
      <p className="text-sm text-gray-500 flex items-center gap-1">
        <ExclamationCircleIcon className="w-4 h-4" />
        {message}
      </p>
    );
  }
  if (status === "declined") {
    return (
      <p className="text-sm text-gray-500 flex items-center gap-1">
        <NoSymbolIcon className="w-4 h-4" />
        {message}
      </p>
    );
  }
  return message;
};
