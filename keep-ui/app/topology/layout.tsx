import { Subtitle, Title } from "@tremor/react";

export default function Layout({ children }: { children: any }) {
  return (
    <main className="p-4 md:p-10 mx-auto max-w-full h-full">
      <Title>Service Topology</Title>
      <Subtitle>
        Data describing the topology of components in your environment.
      </Subtitle>
      {children}
    </main>
  );
}
