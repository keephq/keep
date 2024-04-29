import { Card, Title, Subtitle } from "@tremor/react";


interface Props {
  accessToken: string;
  selectedTab: string;
}


export default function SSOSettings({ accessToken, selectedTab }: Props) {
  return (
    <div className="p-6">
        <Title>SSO Settings</Title>
        <Subtitle>Configure your SSO</Subtitle>
        <Card className="mt-4 p-4">
          <div className="mb-4">
            <label htmlFor="host" className="block text-sm font-medium mb-1">
              Host
            </label>
            </div>
          </Card>
    </div>
  );
}
