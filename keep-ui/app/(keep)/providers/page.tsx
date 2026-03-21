import { useI18n } from "@/i18n/hooks/useI18n";
import ProvidersPage from "./page.client";

export default async function Page(props: {
  searchParams?: Promise<{ [key: string]: string | string[] | undefined }>;
}) {
  const searchParams = await props.searchParams;
  return <ProvidersPage searchParams={searchParams} />;
}

export const metadata = {
  title: "Keep - Providers",
  description: "Connect providers to Keep to make your alerts better.",
};
