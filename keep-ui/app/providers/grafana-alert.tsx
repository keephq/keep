import React from "react";

type GrafanaAlertProps = {
  alert: {
    id: number;
    uid: string;
    orgID: number;
    folderUID: string;
    ruleGroup: string;
    title: string;
    condition: string;
    data: Array<{
      refId: string;
      queryType: string;
      relativeTimeRange: {
        from: number;
        to: number;
      };
      datasourceUid: string;
      model: {
        editorMode: string;
        expr: string;
        intervalMs: number;
        maxDataPoints: number;
        queryType: string;
        refId: string;
      };
    }>;
    updated: string;
    noDataState: string;
    execErrState: string;
    for: string;
    annotations: {
      summary: string;
    };
    labels: {
      [key: string]: string;
    };
    isPaused: boolean;
  };
};

const GrafanaAlert = ({ alert }: GrafanaAlertProps) => {
  const {
    id,
    uid,
    orgID,
    folderUID,
    ruleGroup,
    title,
    condition,
    data,
    updated,
    noDataState,
    execErrState,
    for: alertDuration,
    annotations,
    labels,
    isPaused,
  } = alert;

  return (
    <>
      <td>{alert.id}</td>
      <td>{alert.title}</td>
      <td>{alert.condition}</td>
      <td>{alert.updated}</td>
    </>
  );
};

export default GrafanaAlert;
