import { PageSubtitle, PageTitle } from "@/shared/ui";
import { Card } from "@tremor/react";
import { getTranslations } from "next-intl/server";

export default async function Layout({ children }: { children: any }) {
  const t = await getTranslations("settings");
  return (
    <>
      <main className="flex flex-col h-full">
        <div className="mb-4">
          <PageTitle>{t("title")}</PageTitle>
          <PageSubtitle>{t("subtitle")}</PageSubtitle>
        </div>
        {children}
      </main>
    </>
  );
}
