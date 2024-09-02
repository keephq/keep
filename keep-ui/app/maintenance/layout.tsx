import { Title, Subtitle } from "@tremor/react";
export default function Layout({ children }: { children: any }) {
  return (
    <main className="p-4 md:p-10 mx-auto max-w-full">
      <Title>Maintenance Windows</Title>
      <Subtitle>
        Configure maintenance windows and suppress alerts automatically
      </Subtitle>
      {children}
    </main>
  );
}
