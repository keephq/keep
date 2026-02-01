import {
  CheckCircleIcon,
  ExclamationTriangleIcon,
  NoSymbolIcon,
} from "@heroicons/react/20/solid";

export type SuggestionStatus = "complete" | "error" | "declined";
export type SuggestionResult = {
  status: SuggestionStatus;
  message: string;
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
        <ExclamationTriangleIcon className="w-4 h-4" />
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
