import { Status } from "@/entities/incidents/model";
import { Icon, IconProps } from "@tremor/react";
import {
  CheckCircleIcon,
  ExclamationCircleIcon,
  PauseIcon,
} from "@heroicons/react/24/outline";
import {IoIosGitPullRequest, IoIosTrash} from "react-icons/io";
import React from "react";
import { capitalize } from "@/utils/helpers";

export const STATUS_COLORS = {
  [Status.Firing]: "red",
  [Status.Resolved]: "green",
  [Status.Acknowledged]: "gray",
  [Status.Merged]: "purple",
};

export const STATUS_ICONS = {
  [Status.Firing]: (
    <Icon
      icon={ExclamationCircleIcon}
      tooltip={capitalize(Status.Firing)}
      color="red"
      className="w-4 h-4 mr-2"
    />
  ),
  [Status.Resolved]: (
    <Icon
      icon={CheckCircleIcon}
      tooltip={capitalize(Status.Resolved)}
      color="green"
      className="w-4 h-4 mr-2"
    />
  ),
  [Status.Acknowledged]: (
    <Icon
      icon={PauseIcon}
      tooltip={capitalize(Status.Acknowledged)}
      color="gray"
      className="w-4 h-4 mr-2"
    />
  ),
  [Status.Merged]: (
    <Icon
      icon={IoIosGitPullRequest}
      tooltip={capitalize(Status.Merged)}
      color="purple"
      className="w-4 h-4 mr-2"
    />
  ),
  [Status.Deleted]: (
    <Icon
      icon={IoIosTrash}
      tooltip={capitalize(Status.Deleted)}
      color="gray"
      className="w-4 h-4 mr-2"
    />
  ),
};

export function StatusIcon({
  status,
  ...props
}: { status: Status } & Omit<IconProps, "icon" | "color">) {
  switch (status) {
    default:
    case Status.Firing:
      return <Icon icon={ExclamationCircleIcon} color="red" {...props} />;
    case Status.Resolved:
      return <Icon icon={CheckCircleIcon} color="green" {...props} />;
    case Status.Acknowledged:
      return <Icon icon={PauseIcon} color="gray" {...props} />;
    case Status.Merged:
      return <Icon icon={IoIosGitPullRequest} color="purple" {...props} />;
  }
}
