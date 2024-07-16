import { Callout, Title } from "@tremor/react";
import { IncidentDto } from "../model";
import { RiSparkling2Line } from "react-icons/ri";

interface Props {
  incident: IncidentDto;
}

export default function IncidentInformation({ incident }: Props) {
  return (
    <div className="flex h-full flex-col justify-between">
      <div>
        <Title className="mb-2.5">⚔️ Incident Information</Title>
        <div className="prose-2xl">{incident.name}</div>
        <p>Description: {incident.description}</p>
        <p>Started at: {incident.start_time?.toISOString() ?? "N/A"}</p>
        <Callout
          title="AI Summary"
          color="gray"
          icon={RiSparkling2Line}
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
      </div>
    </div>
  );
}
