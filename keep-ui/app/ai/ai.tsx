"use client";
import { Card, List, ListItem, Title, Subtitle } from "@tremor/react";
import { useAIStats } from "utils/hooks/useAIStats";

export default function Ai() {
  const { data: aistats, isLoading } = useAIStats();

  return (
    <main className="p-4 md:p-10 mx-auto max-w-full">
      <div className="flex justify-between items-center">
        <div>
          <Title>AI Correlation</Title>
          <Subtitle>
            Correlating alerts to incidents based on past alerts, incidents, and
            the other data.
          </Subtitle>
        </div>
      </div>
      <Card className="mt-10 p-4 md:p-10 mx-auto">
        <div>
          <div className="prose-2xl">👋 You are almost there!</div>
          AI Correlation is coming soon. Make sure you have enough data collected to prepare.
          <div className="max-w-md mt-10 flex justify-items-start justify-start">
            <List>
              <ListItem>
                <span>
                  Connect an incident source to dump incidents, or create 10
                  incidents manually
                </span>
                <span>
                  {aistats?.incidents_count &&
                  aistats?.incidents_count >= 10 ? (
                    <div>✅</div>
                  ) : (
                    <div>⏳</div>
                  )}
                </span>
              </ListItem>
              <ListItem>
                <span>Collect 100 alerts</span>
                <span>
                  {aistats?.alerts_count && aistats?.alerts_count >= 100 ? (
                    <div>✅</div>
                  ) : (
                    <div>⏳</div>
                  )}
                </span>
              </ListItem>
              <ListItem>
                <span>Collect alerts for more than 3 days</span>
                <span>
                  {aistats?.first_alert_datetime && new Date(aistats.first_alert_datetime) < new Date(Date.now() - 3 * 24 * 60 * 60 * 1000) ? (
                    <div>✅</div>
                  ) : (
                    <div>⏳</div>
                  )}
                </span>
              </ListItem>
            </List>
          </div>
        </div>
      </Card>
    </main>
  );
}
