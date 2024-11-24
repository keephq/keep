import { Title, Subtitle } from "@tremor/react";
export default function Layout({ children }: { children: any }) {
  return (
    <main className="p-4 md:p-10 mx-auto max-w-full">
      <Title>Mapping</Title>
      <Subtitle>
        Enirch alerts with more data from Topology, CSV, JSON and YAMLs
      </Subtitle>
      {children}
    </main>
  );
}
