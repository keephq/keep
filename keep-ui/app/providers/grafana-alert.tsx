import React from 'react';

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
    <div className="grafana-alert">
      <h2>{title}</h2>
      <p>Rule Group: {ruleGroup}</p>
      <p>Condition: {condition}</p>
      <p>No Data State: {noDataState}</p>
      <p>Execution Error State: {execErrState}</p>
      <p>Alert Duration: {alertDuration}</p>
      <p>Updated: {updated}</p>
      <p>Annotations: {annotations.summary}</p>
      <p>Labels:</p>
      <ul>
        {Object.entries(labels).map(([key, value]) => (
          <li key={key}>
            {key}: {value}
          </li>
        ))}
      </ul>
      <p>Is Paused: {isPaused ? 'Yes' : 'No'}</p>
    </div>
  );
};

export default GrafanaAlert;
