'use client';
import PageClient from "./page.client";
import { Suspense } from "react";
import Loading from "../loading";
import ErrorBoundary from "../error-boundary";

export default function Page() {
  return (
    <>
      <div>
        <ErrorBoundary fallback={<p>l</p>}>
          <Suspense fallback={<Loading/>}>
            <PageClient />
          </Suspense>
        </ErrorBoundary>
      </div>
    </>
  );
}
