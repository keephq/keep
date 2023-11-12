import { Title, Subtitle } from "@tremor/react";

export default function Layout({ children }: { children: any }) {
  return (
    <>
      <main className="p-4 md:p-10 mx-auto max-w-full">
        <Title>Alerts</Title>
        <Subtitle>
          A single pane of glass for all your different alert providers
        </Subtitle>
        {children}
      </main>
    </>
  );
}
