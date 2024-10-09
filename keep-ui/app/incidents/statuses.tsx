import { Status } from "@/app/incidents/models";
import { Icon } from "@tremor/react";
import {
  CheckCircleIcon,
  ExclamationCircleIcon,
  PauseIcon,
} from "@heroicons/react/24/outline";
import React from "react";

export const STATUS_ICONS = {
  [Status.Firing]: (
    <Icon
      icon={ExclamationCircleIcon}
      tooltip={Status.Firing}
      color="red"
      className="w-4 h-4 mr-2"
    />
  ),
  [Status.Resolved]: (
    <Icon
      icon={CheckCircleIcon}
      tooltip={Status.Resolved}
      color="green"
      className="w-4 h-4 mr-2"
    />
  ),
  [Status.Acknowledged]: (
    <Icon
      icon={PauseIcon}
      tooltip={Status.Acknowledged}
      color="gray"
      className="w-4 h-4 mr-2"
    />
  ),
};
