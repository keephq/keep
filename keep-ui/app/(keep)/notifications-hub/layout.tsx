import { Title, Subtitle } from "@tremor/react";

export default function Layout({ children }: { children: any }) {
  return (
    <>
      <main className="p-4 md:p-10 mx-auto max-w-full">
        <Title>Notifications Hub</Title>
        <Subtitle>
          A single pane for everything related with notifications
        </Subtitle>
        {children}
      </main>
    </>
  );
}
