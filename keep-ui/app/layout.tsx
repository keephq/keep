import { NextAuthProvider } from "./auth-provider";
import ErrorBoundary from "./error-boundary";
import Frill from "./frill";
import "./globals.css";

import Nav from "./nav";

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      className="h-full bg-gray-50"
      suppressHydrationWarning={true}
    >
      <body className="h-full">
        <Frill />
        <NextAuthProvider>
          {/* @ts-expect-error Server Component */}
          <Nav />
          {/* https://discord.com/channels/752553802359505017/1068089513253019688/1117731746922893333 */}
          <ErrorBoundary>{children}</ErrorBoundary>
        </NextAuthProvider>
      </body>
    </html>
  );
}
