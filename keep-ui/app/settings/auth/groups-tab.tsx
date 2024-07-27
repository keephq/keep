import { Title, Subtitle, Card } from "@tremor/react";

interface Props {
  accessToken: string;
}

export default function GroupsSubTab({ accessToken }: Props) {
  return (
    <div className="mt-10">
      <Title>Groups Management</Title>
      <Subtitle>Manage user groups</Subtitle>
      <Card className="mt-2.5">
        {/* Add groups management functionality here */}
        <p>Groups management functionality to be implemented.</p>
      </Card>
    </div>
  );
}
