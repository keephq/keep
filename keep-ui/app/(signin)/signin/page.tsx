"use client";
import SignInForm from "./SignInForm";

export type SignInPageProps = {
  params: {
    amt: string;
  };
  searchParams: {
    callbackUrl?: string;
  };
};

export default function SignInPage({ params, searchParams }: SignInPageProps) {
  return <SignInForm params={params} searchParams={searchParams} />;
}
