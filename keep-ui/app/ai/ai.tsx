"use client";
import {
  Card,
  List,
  ListItem,
  Title,
  Subtitle,
} from "@tremor/react";
import { LineChart } from '@tremor/react';
import { useExtractions } from "utils/hooks/useExtractionRules";


const chartdata = [
  {
    date: 'Day 1',
    'Your data correlation accuracy': 4,
    'Average Keep customer\'s correlation accuracy': 4,
  },
  {
    date: 'Day 2',
    'Your data correlation accuracy': 12,
    'Average Keep customer\'s correlation accuracy': 9,
  },
  {
    date: 'Day 3',
    'Your data correlation accuracy': 15,
    'Average Keep customer\'s correlation accuracy': 12,
  },
  {
    date: 'Day 4',
    'Your data correlation accuracy': 19,
    'Average Keep customer\'s correlation accuracy': 23,
  },
  {
    date: 'Day 5',
    'Your data correlation accuracy': 22,
    'Average Keep customer\'s correlation accuracy': 43,
  },
  {
    date: 'Day 6',
    'Your data correlation accuracy': 32,
    'Average Keep customer\'s correlation accuracy': 47,
  },
  {
    date: 'Day 7',
    'Your data correlation accuracy': 42,
    'Average Keep customer\'s correlation accuracy': 76,
  },
]

const valueFormatter = function (number: number) {
  return  number.toString() + '%';
};


export default function Ai() {
  const { data: extractions, isLoading } = useExtractions();
  return (
    <main className="p-4 md:p-10 mx-auto max-w-full">
      <div className="flex justify-between items-center">
        <div>
          <Title>AI Correlation</Title>
          <Subtitle>
            Correlating alerts to incidents based on past alerts, incidents, and the other data.
          </Subtitle>
        </div>
      </div>
      <Card className="mt-10 p-4 md:p-10 mx-auto">
      <div className="prose-2xl">👋 You are almost there!</div>
      In order to use AI Correlation, you need to provide some data to the engine so it will learn about your infrastructure and alerts.
      <div className="mx-auto max-w-md mt-10">
        <List>
          <ListItem>
            <span>Connect alert source</span>
            <span>✅</span>
          </ListItem>
          <ListItem>
            <span>Connect an incident source or create 10 incidents manually</span>
            <span>⏳</span>
          </ListItem>
          <ListItem>
            <span>Collect 100 alerts</span>
            <span>⏳</span>
          </ListItem>
          <ListItem>
            <span>Collect alerts for 3 days</span>
            <span>✅</span>
          </ListItem>
        </List>
      </div>
      
      <LineChart
        className="mt-4 h-72"
        data={chartdata}
        index="date"
        yAxisWidth={65}
        categories={['Your data correlation accuracy', 'Average Keep customer\'s correlation accuracy']}
        colors={['indigo', 'cyan']}
        valueFormatter={valueFormatter}
        />
      </Card>
    </main>
  );
}
