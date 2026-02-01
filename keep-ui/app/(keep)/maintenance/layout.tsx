import { PageTitle, PageSubtitle } from "@/shared/ui";
export default function Layout({ children }: { children: any }) {
  return (
    <main className="mx-auto max-w-full flex flex-col gap-6">
      <header>
        <PageTitle>Maintenance Windows</PageTitle>
        <PageSubtitle>
          Configure maintenance windows and suppress alerts automatically
        </PageSubtitle>
      </header>

      {children}
    </main>
  );
}
