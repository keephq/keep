import { NextAuthProvider } from "./auth-provider";
import ErrorBoundary from "./error-boundary";
import { Intercom } from "@/components/ui/Intercom";
import { Mulish } from "next/font/google";
import { Card } from "@tremor/react";

import "./globals.css";
import "react-toastify/dist/ReactToastify.css";

// If loading a variable font, you don't need to specify the font weight
const mulish = Mulish({
  subsets: ["latin"],
  display: "swap",
});

import { ToastContainer } from "react-toastify";
import Navbar from "./navbar";

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      className={`h-full bg-gray-50 ${mulish.className}`}
      suppressHydrationWarning={true}
    >
      <body className="h-full">
        <NextAuthProvider>
          <Navbar />
          {/* https://discord.com/channels/752553802359505017/1068089513253019688/1117731746922893333 */}
          <ErrorBoundary>{children}</ErrorBoundary>
        </NextAuthProvider>
        <ToastContainer />

        {/** footer */}
        {process.env.GIT_COMMIT_HASH ? (
          <div className="fixed right-2.5 bottom-2.5 text-gray-500 text-sm">
            Build: {process.env.GIT_COMMIT_HASH}
          </div>
        ) : (
          <Intercom />
        )}
      </body>
    </html>
  );
}
