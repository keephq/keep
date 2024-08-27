import { Card, Title, Subtitle } from "@tremor/react";

export default function Layout({ children }: { children: any }) {
  return (
    <>
<<<<<<< HEAD
      <main className="flex flex-col h-screen p-4 md:p-10">
        <div className="mb-4">
          <Title>Settings</Title>
          <Subtitle>Setup and configure Keep</Subtitle>
        </div>
        <Card className="flex-grow overflow-auto">{children}</Card>
=======
      <main className="p-4 mx-auto max-w-7xl">
        <Title>Settings</Title>
        <Subtitle>Setup and configure Keep</Subtitle>
        <Card className="card-container mt-10">{children}</Card>
>>>>>>> main
      </main>
    </>
  );
}
