import { FrigadeProvider, FrigadeAnnouncement } from "@frigade/react";
import { getServerSession } from "utils/customAuth";
import { authOptions } from "pages/api/auth/[...nextauth]";
import ProvidersPage from "./page.client";
import Cookies from "js-cookie";

export default async function Page({
  searchParams,
}: {
  searchParams?: { [key: string]: string };
}) {
  const session = await getServerSession(authOptions);
  return (
    <FrigadeProvider
      publicApiKey="api_public_6BKR7bUv0YZ5dqnjLGeHpRWCHaDWeb5cVobG3A9YkW0gOgafOEBvtJGZgvhp8PGb"
      userId={session?.user?.email || Cookies.get("anonymousId")}
      config={{
        debug: true,
        defaultAppearance: { theme: { colorPrimary: "#F97316" } },
      }}
    >
      <FrigadeAnnouncement
        flowId="flow_VpefBUPWpliWceBm"
        modalPosition="center"
      />
      <ProvidersPage searchParams={searchParams} />
    </FrigadeProvider>
  );
}

export const metadata = {
  title: "Keep - Providers",
  description: "Connect providers to Keep to make your alerts better.",
};
