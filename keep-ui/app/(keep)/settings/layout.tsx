import { Card, Title, Subtitle } from "@tremor/react";

export default function Layout({ children }: { children: any }) {
  return (
    <>
      <main className="flex flex-col h-full">
        <div className="mb-4">
          <Title>Settings</Title>
          <Subtitle>Setup and configure Keep</Subtitle>
        </div>
        <Card className="flex-grow overflow-auto">{children}</Card>
      </main>
    </>
  );
}
