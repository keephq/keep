import { AtSymbolIcon } from "@heroicons/react/24/outline";
import { Title, Subtitle, Card, Callout } from "@tremor/react";

export const UsersSettings = () => {
  return (
    <div className="mt-2.5">
      <Title>Users Management</Title>
      <Subtitle>Add or remove users from your tenant</Subtitle>
      <Card className="mt-2.5">
        <Callout title="Coming soon" icon={AtSymbolIcon} color="yellow">
          Users management page is currently under construction. <br />
          To add/remove users, reach out to us via{" "}
          <a
            href="https://slack.keephq.dev/"
            target="_blank"
            className="underline"
          >
            Slack
          </a>
          .
        </Callout>
      </Card>
    </div>
  );
};
