import { useI18n } from "@/i18n/hooks/useI18n";
import { Card } from "@tremor/react";

export default function Page() {
  const { t } = useI18n();
  return (
    <Card className="mt-10 p-4 md:p-10 mx-auto">
      <div>{t("notificationsHub.comingSoon")}</div>
    </Card>
  );
}

export const metadata = {
  title: "Keep - Notifications Hub",
  description: "Manage everything related with notifications.",
};
