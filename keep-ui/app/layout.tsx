import { ReactNode } from "react";
import { NextAuthProvider } from "./auth-provider";
import ErrorBoundary from "./error-boundary";
import { Intercom } from "@/components/ui/Intercom";
import { Mulish } from "next/font/google";

import "./globals.css";
import "react-toastify/dist/ReactToastify.css";

// If loading a variable font, you don't need to specify the font weight
const mulish = Mulish({
  subsets: ["latin"],
  display: "swap",
});

import { ToastContainer } from "react-toastify";
import Navbar from "components/navbar/Navbar";

type RootLayoutProps = {
  children: ReactNode;
};

export default async function RootLayout({ children }: RootLayoutProps) {
  return (
    <html lang="en" className={`bg-gray-50 ${mulish.className}`}>
      <body className="h-screen flex flex-col lg:grid lg:grid-cols-[fit-content(250px)_30px_auto] lg:grid-rows-1 lg:has-[aside[data-minimized='true']]:grid-cols-[0px_30px_auto]">
        <NextAuthProvider>
          {/* @ts-ignore-error Server Component */}
          <Navbar />
          {/* https://discord.com/channels/752553802359505017/1068089513253019688/1117731746922893333 */}
          <main className="flex flex-col col-start-3 p-4 overflow-auto">
            <div className="flex-1 h-0">
              <ErrorBoundary>{children}</ErrorBoundary>
            </div>
            <ToastContainer />
          </main>
        </NextAuthProvider>

        {/** footer */}
        {process.env.GIT_COMMIT_HASH ? (
          <div className="fixed right-2.5 bottom-2.5 text-gray-500 text-sm">
            Build: {process.env.GIT_COMMIT_HASH}
            Version: {process.env.KEEP_VERSION}
          </div>
        ) : (
          <Intercom />
        )}
      </body>
    </html>
  );
}
