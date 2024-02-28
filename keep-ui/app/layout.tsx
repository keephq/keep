import { ReactNode } from "react";

import ErrorBoundary from "./error-boundary";
import { Intercom } from "@/components/ui/Intercom";
import { Mulish } from "next/font/google";
import { ToastContainer } from "react-toastify";
import Navbar from "components/navbar/Navbar";
import "react-toastify/dist/ReactToastify.css";
import "./globals.css";
import { Providers } from "./Providers";

// If loading a variable font, you don't need to specify the font weight
const mulish = Mulish({
  subsets: ["latin"],
  display: "swap",
});

type RootLayoutProps = {
  children: ReactNode;
};

export default async function RootLayout({ children }: RootLayoutProps) {
  return (
    <html lang="en" className={mulish.className} suppressHydrationWarning>
      <body className="bg-gray-50 dark:bg-gray-900 h-screen flex flex-col lg:grid lg:grid-cols-[fit-content(250px)_30px_auto] lg:grid-rows-1 lg:has-[aside[data-minimized='true']]:grid-cols-[0px_30px_auto]">
        <Providers>
          {/* @ts-ignore-error Server Component */}
          <Navbar />
          <main className="flex flex-col col-start-3 p-4 overflow-auto">
            <div className="flex-1 h-0">
              <ErrorBoundary>{children}</ErrorBoundary>
            </div>
            <ToastContainer />
          </main>
        </Providers>

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
