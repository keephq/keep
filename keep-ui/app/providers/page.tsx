'use client';
import { Suspense } from "react";
import Loading from "../loading";
import ErrorBoundary from "../error-boundary";
import ProvidersPage from "./page.client";


export default function Page() {
  return (
    <>
      <div>
        <ErrorBoundary>
          <Suspense fallback={<Loading/>}>
            <ProvidersPage />
          </Suspense>
        </ErrorBoundary>
      </div>
    </>
  );
}
