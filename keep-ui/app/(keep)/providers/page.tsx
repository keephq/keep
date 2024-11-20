import ProvidersPage from "./page.client";

export default async function Page({
  searchParams,
}: {
  searchParams?: { [key: string]: string };
}) {
  return <ProvidersPage searchParams={searchParams} />;
}

export const metadata = {
  title: "Keep - Providers",
  description: "Connect providers to Keep to make your alerts better.",
};
