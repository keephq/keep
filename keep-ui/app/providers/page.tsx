import { getServerSession } from "next-auth/next";
import { authOptions } from "pages/api/auth/[...nextauth]";
import ProvidersPage from "./page.client";

export default async function Page({
  searchParams,
}: {
  searchParams?: { [key: string]: string };
}) {
  const session = await getServerSession(authOptions);
  return <ProvidersPage searchParams={searchParams} />;
}

export const metadata = {
  title: "Keep - Providers",
  description: "Connect providers to Keep to make your alerts better.",
};
