import { Callout, Subtitle, Title, Text, BarChart } from "@tremor/react";
import { IncidentDto } from "../model";
import { Ai } from "components/icons";

interface Props {
  incident: IncidentDto;
}

const chartdata = [
  {
    name: "Topic 1",
    "Group A": 890,
    "Group B": 338,
    "Group C": 538,
    "Group D": 396,
    "Group E": 138,
    "Group F": 436,
  },
  {
    name: "Topic 2",
    "Group A": 289,
    "Group B": 233,
    "Group C": 253,
    "Group D": 333,
    "Group E": 133,
    "Group F": 533,
  },
  {
    name: "Topic 3",
    "Group A": 380,
    "Group B": 535,
    "Group C": 352,
    "Group D": 718,
    "Group E": 539,
    "Group F": 234,
  },
  {
    name: "Topic 4",
    "Group A": 90,
    "Group B": 98,
    "Group C": 28,
    "Group D": 33,
    "Group E": 61,
    "Group F": 53,
  },
];

const dataFormatter = (number: number) =>
  Intl.NumberFormat("us").format(number).toString();

export function CorrelatedAlerts() {
  return (
    <>
      <h3 className="text-lg font-medium text-tremor-content-strong dark:text-dark-tremor-content-strong">
        Correlated Alerts Windows
      </h3>
      <BarChart
        className="mt-6"
        data={chartdata}
        index="name"
        categories={[
          "Group A",
          "Group B",
          "Group C",
          "Group D",
          "Group E",
          "Group F",
        ]}
        colors={["blue", "teal", "amber", "rose", "indigo", "emerald"]}
        valueFormatter={dataFormatter}
        yAxisWidth={48}
      />
    </>
  );
}

export default function IncidentInformation({ incident }: Props) {
  return (
    <div className="flex h-full flex-col justify-between">
      <div>
        <Title className="mb-2.5">Incident Information</Title>
        <Subtitle>{incident.name}</Subtitle>
        <Text>Description: {incident.description}</Text>
        <Text className="mb-5">
          Started at: {incident.start_time?.toISOString() ?? "N/A"}
        </Text>
        <Callout
          title="AI Summary"
          color="gray"
          icon={Ai}
          className="mt-10 mb-10"
        >
          Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do
          eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad
          minim veniam, quis nostrud exercitation ullamco laboris nisi ut
          aliquip ex ea commodo consequat. Duis aute irure dolor in
          reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla
          pariatur. Excepteur sint occaecat cupidatat non proident, sunt in
          culpa qui officia deserunt mollit anim id est laborum.
        </Callout>
        <CorrelatedAlerts />
      </div>
    </div>
  );
}
