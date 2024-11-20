import { ReactNode } from "react";
import { NextAuthProvider } from "../auth-provider";
import { Mulish } from "next/font/google";
import { ToastContainer } from "react-toastify";
import Navbar from "components/navbar/Navbar";
import { TopologyPollingContextProvider } from "@/app/(keep)/topology/model/TopologyPollingContext";
import { FrigadeProvider } from "../frigade-provider";
import { getConfig } from "@/shared/lib/server/getConfig";
import { ConfigProvider } from "../config-provider";
import "../globals.css";
import "react-toastify/dist/ReactToastify.css";
import { PHProvider } from "../posthog-provider";
import dynamic from "next/dynamic";
import ReadOnlyBanner from "../read-only-banner";
import { headers } from "next/headers";

const PostHogPageView = dynamic(() => import("@/shared/ui/PostHogPageView"), {
  ssr: false,
});

// If loading a variable font, you don't need to specify the font weight
const mulish = Mulish({
  subsets: ["latin"],
  display: "swap",
});

type RootLayoutProps = {
  children: ReactNode;
};

export default async function RootLayout({ children }: RootLayoutProps) {
  const config = getConfig();
  // const headersList = headers();
  // const header_url = headersList.get('x-url') || "";
  // const isSignIn = header_url.includes("/signin");
  // console.log("isSignIn", isSignIn);
  // console.log("header_url", header_url);
  return (
    <html lang="en" className={`bg-gray-50 ${mulish.className}`}>
      <body className="h-screen flex flex-col lg:grid lg:grid-cols-[fit-content(250px)_30px_auto] lg:grid-rows-1 lg:has-[aside[data-minimized='true']]:grid-cols-[0px_30px_auto]">
        <ConfigProvider config={config}>
          <PHProvider>
            <NextAuthProvider>
              <TopologyPollingContextProvider>
                <FrigadeProvider>
                  {/* @ts-ignore-error Server Component */}
                  <PostHogPageView />
                  {/* dont show navbar on signin */}
                  <Navbar />
                  {/* https://discord.com/channels/752553802359505017/1068089513253019688/1117731746922893333 */}
                  <main className="page-container flex flex-col col-start-3 overflow-auto">
                    {/* Add the banner here, before the navbar */}
                    {config.READ_ONLY && <ReadOnlyBanner />}
                    <div className="flex-1">{children}</div>
                    <ToastContainer />
                  </main>
                </FrigadeProvider>
              </TopologyPollingContextProvider>
            </NextAuthProvider>
          </PHProvider>
        </ConfigProvider>

        {/** footer */}
        {process.env.GIT_COMMIT_HASH && (
          <div className="fixed right-2.5 bottom-2.5 text-gray-500 text-sm">
            Build: {process.env.GIT_COMMIT_HASH}
            <br />
            Version: {process.env.KEEP_VERSION}
          </div>
        )}
      </body>
    </html>
  );
}
