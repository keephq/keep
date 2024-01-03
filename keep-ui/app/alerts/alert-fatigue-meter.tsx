import { CategoryBar } from "@tremor/react";
import { AlertDto } from "./models";
import { calculateFatigue } from "utils/fatigue";
import { useEffect, useMemo, useState } from "react";

const oneHourAgo = new Date().getTime() - 60 * 60 * 1000; // Current time - 1 hour

interface AlertFatigueProps {
  alerts?: AlertDto[];
}

export default function AlertFatigueMeter({ alerts }: AlertFatigueProps) {
  const fatigueScore = useMemo(() => calculateFatigueScore(alerts), [alerts]);

  return (
    <CategoryBar
      values={[40, 30, 20, 10]}
      colors={["emerald", "yellow", "orange", "rose"]}
      markerValue={fatigueScore}
      tooltip={`${fatigueScore}% in the last hour`}
      showLabels={false}
      className="min-w-[192px]"
      showAnimation={true}
    />
  );
}

const calculateFatigueScore = (alerts: AlertDto[] | undefined): number => {
  const lastHourAlerts = alerts?.filter((alert) => {
    return alert.lastReceived.getTime() > oneHourAgo;
  });
  if (lastHourAlerts && lastHourAlerts.length > 0) {
    const { fatigueScore } = calculateFatigue(lastHourAlerts)[0];
    return fatigueScore;
  }
  return 0;
};
