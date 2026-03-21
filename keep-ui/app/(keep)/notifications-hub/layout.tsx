import { useI18n } from "@/i18n/hooks/useI18n";
import { Title, Subtitle } from "@tremor/react";

export default function Layout({ children }: { children: any }) {
  const { t } = useI18n();
  return (
    <>
      <main className="p-4 md:p-10 mx-auto max-w-full">
        <Title>{t("notificationsHub.title")}</Title>
        <Subtitle>
          {t("notificationsHub.description")}
        </Subtitle>
        {children}
      </main>
    </>
  );
}
