import { NextAuthProvider } from "./auth-provider";
import Frill from "./frill";
import "./globals.css";

import Nav from "./nav";

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {

  return (
    <html lang="en" className="h-full bg-gray-50" suppressHydrationWarning={true}>
      <body className="h-full">
        <Frill />
        <NextAuthProvider>
          {/* @ts-expect-error Server Component */}
          <Nav />
          {children}
        </NextAuthProvider>
      </body>
    </html>
  );
}
