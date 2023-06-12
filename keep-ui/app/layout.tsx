import { NextAuthProvider } from "./auth-provider";
import "./globals.css";

import Nav from "./nav";

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="h-full bg-gray-50">
      <body className="h-full">
        <NextAuthProvider>
          {/* @ts-expect-error Server Component */}
          <Nav />
          {children}
        </NextAuthProvider>
      </body>
    </html>
  );
}
