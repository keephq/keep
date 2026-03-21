import { useI18n } from "@/i18n/hooks/useI18n";
import { PageTitle, PageSubtitle } from "@/shared/ui";
import { getTranslations } from "next-intl/server";

export default async function Layout({ children }: { children: any }) {
  const t = await getTranslations();
  
  return (
    <main className="mx-auto max-w-full flex flex-col gap-6">
      <header>
        <PageTitle>{t("maintenance.title")}</PageTitle>
        <PageSubtitle>
          {t("maintenance.description")}
        </PageSubtitle>
      </header>

      {children}
    </main>
  );
}
