import {
  CheckCircleIcon,
  NoSymbolIcon,
  XCircleIcon,
} from "@heroicons/react/20/solid";

export function getIconForStatusString(status: string) {
  let icon;
  switch (status) {
    case "success":
      icon = <CheckCircleIcon className="size-6 cover text-green-500" />;
      break;
    case "skipped":
      icon = (
        <NoSymbolIcon className="size-6 cover text-slate-500" title="Skipped" />
      );
      break;
    case "failed":
    case "fail":
    case "failure":
    case "error":
    case "timeout":
      icon = <XCircleIcon className="size-6 cover text-red-500" />;
      break;
    case "in_progress":
      icon = <div className="loader"></div>;
      break;
    default:
      icon = <div className="loader"></div>;
  }
  return icon;
}
