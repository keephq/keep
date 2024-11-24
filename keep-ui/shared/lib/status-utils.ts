import {
  ExclamationCircleIcon,
  CheckCircleIcon,
  CircleStackIcon,
} from "@heroicons/react/24/outline";

export const getStatusIcon = (status: string) => {
  switch (status.toLowerCase()) {
    case "firing":
      return ExclamationCircleIcon;
    case "resolved":
      return CheckCircleIcon;
    case "acknowledged":
      return CircleStackIcon;
    default:
      return CircleStackIcon;
  }
};

export const getStatusColor = (status: string) => {
  switch (status.toLowerCase()) {
    case "firing":
      return "red";
    case "resolved":
      return "green";
    case "acknowledged":
      return "blue";
    default:
      return "gray";
  }
};
