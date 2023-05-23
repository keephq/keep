import './globals.css';

import Nav from './nav';
import { Suspense } from 'react';


export default async function RootLayout({
  children
}: {
  children: React.ReactNode;
}) {

  return (
    <html lang="en" className="h-full bg-gray-50">
        <body className="h-full">
            <Suspense fallback="...">
              {/* @ts-expect-error Server Component */}
              <Nav />
            </Suspense>
          {children}
        </body>
    </html>
  );
}
