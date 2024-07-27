import { Title, Subtitle, Card } from "@tremor/react";

interface Props {
  accessToken: string;
}

export default function RolesSubTab({ accessToken }: Props) {
  return (
    <div className="mt-10">
      <Title>Roles Management</Title>
      <Subtitle>Manage user roles and permissions</Subtitle>
      <Card className="mt-2.5">
        {/* Add roles management functionality here */}
        <p>Roles management functionality to be implemented.</p>
      </Card>
    </div>
  );
}
