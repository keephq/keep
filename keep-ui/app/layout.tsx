import { ReactNode } from "react";
import { NextAuthProvider } from "./auth-provider";
import { Mulish } from "next/font/google";
import { ToastContainer } from "react-toastify";
import Navbar from "components/navbar/Navbar";
import { TopologyPollingContextProvider } from "@/app/topology/model/TopologyPollingContext";
import { FrigadeProvider } from "./frigade-provider";
import { getConfig } from "@/shared/lib/server/getConfig";
import { ConfigProvider } from "./config-provider";
import "./globals.css";
import "react-toastify/dist/ReactToastify.css";

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
  return (
    <html lang="en" className={`bg-gray-50 ${mulish.className}`}>
      <body className="h-screen flex flex-col lg:grid lg:grid-cols-[fit-content(250px)_30px_auto] lg:grid-rows-1 lg:has-[aside[data-minimized='true']]:grid-cols-[0px_30px_auto]">
        <ConfigProvider config={config}>
          <NextAuthProvider>
            <TopologyPollingContextProvider>
              <FrigadeProvider>
                {/* @ts-ignore-error Server Component */}
                <Navbar />
                {/* https://discord.com/channels/752553802359505017/1068089513253019688/1117731746922893333 */}
                <main className="page-container flex flex-col col-start-3 overflow-auto">
                  <div className="flex-1">{children}</div>
                  <ToastContainer />
                </main>
              </FrigadeProvider>
            </TopologyPollingContextProvider>
          </NextAuthProvider>
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
