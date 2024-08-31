import { Card, Title, Subtitle } from "@tremor/react";

export default function Layout({ children }: { children: any }) {
  return (
    <>
      <main className="p-4 mx-auto max-w-7xl">
        <Title>Settings</Title>
        <Subtitle>Setup and configure Keep</Subtitle>
        <Card className="card-container mt-10">{children}</Card>
      </main>
    </>
  );
}
