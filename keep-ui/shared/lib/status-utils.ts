import {
  ExclamationCircleIcon,
  CheckCircleIcon,
  CircleStackIcon,
  PauseIcon,
} from "@heroicons/react/24/outline";
import { IoIosGitPullRequest } from "react-icons/io";

export const getStatusIcon = (status: string) => {
  switch (status.toLowerCase()) {
    case "firing":
      return ExclamationCircleIcon;
    case "resolved":
      return CheckCircleIcon;
    case "acknowledged":
      return PauseIcon;
    case "merged":
      return IoIosGitPullRequest;
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
      return "gray";
    case "merged":
      return "purple";
    default:
      return "gray";
  }
};
