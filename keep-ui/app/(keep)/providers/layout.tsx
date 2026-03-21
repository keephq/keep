"use client";
import { useI18n } from "@/i18n/hooks/useI18n";
import { PropsWithChildren } from "react";
import { ProvidersFilterByLabel } from "./components/providers-filter-by-label";
import { ProvidersSearch } from "./components/providers-search";
import { FilerContextProvider } from "./filter-context";
import { ProvidersCategories } from "./components/providers-categories";
import { PageSubtitle, PageTitle } from "@/shared/ui";

export default function ProvidersLayout({ children }: PropsWithChildren) {
  const { t } = useI18n();
  return (
    <FilerContextProvider>
      <div className="flex flex-col gap-6">
        <header>
          <PageTitle>{t("providers.layout.title")}</PageTitle>
          <PageSubtitle>
            {t("providers.layout.subtitle")}
          </PageSubtitle>
        </header>
        <main>
          <div className="flex w-full flex-col items-center mb-4">
            <div className="flex w-full">
              <ProvidersSearch />
              <ProvidersFilterByLabel />
            </div>
            <ProvidersCategories />
          </div>
          <div className="flex flex-col">{children}</div>
        </main>
      </div>
    </FilerContextProvider>
  );
}
