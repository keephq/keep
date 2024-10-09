import React from "react";

type DatadogAlertProps = {
  alert: {
    id: number;
    created: string;
    creator: {
      id: number;
      email: string;
      handle: string;
      name: string;
    };
    modified: string;
    message: string;
    overall_state_modified: string;
    multi: boolean;
    name: string;
    options: {
      restriction_query: null | string;
      enable_logs_sample: boolean;
      groupby_simple_monitor: boolean;
      include_tags: boolean;
      new_host_delay: number;
      // Include other option fields as needed
    };
    org_id: number;
    overall_state: string;
    priority: null | string;
    query: string;
    restricted_roles: null;
    tags: string[];
    type: string;
    // Include other fields as needed
  };
};

const DatadogAlert = ({ alert }: DatadogAlertProps) => {
  const {
    id,
    created,
    creator,
    modified,
    message,
    overall_state_modified,
    multi,
    name,
    options,
    org_id,
    overall_state,
    priority,
    query,
    tags,
    type,
    // Destructure other fields
  } = alert;

  return (
    <>
      <td>{alert.id}</td>
      <td>{alert.name}</td>
      <td>{alert.query}</td>
      <td>{alert.modified}</td>
    </>
  );
};

export default DatadogAlert;
