import {
  ExclamationCircleIcon,
  CheckCircleIcon,
  CircleStackIcon,
  PauseIcon,
  SpeakerWaveIcon,
} from "@heroicons/react/24/outline";
import { IoIosGitPullRequest } from "react-icons/io";

/**
 * Maps an alert/incident status string to the appropriate icon component
 * 
 * @param status - The status string to convert to an icon
 * @param isNoisy - Whether the alert is noisy (optional)
 * @returns A React icon component based on the status
 * 
 * @example
 * const AlertIcon = getStatusIcon("firing");
 * // Returns ExclamationCircleIcon
 */
export const getStatusIcon = (status: string, isNoisy?: boolean) => {
  switch (status.toLowerCase()) {
    case "firing":
      return isNoisy ? SpeakerWaveIcon : ExclamationCircleIcon;
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

/**
 * Maps an alert/incident status string to an appropriate color
 * 
 * @param status - The status string to convert to a color
 * @returns A color string (compatible with Tailwind CSS and Tremor)
 * 
 * @example
 * const badgeColor = getStatusColor("firing");
 * // Returns "red"
 */
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
