"use client";
import SignInForm from "./SignInForm";

export default function SignInPage({
  params,
  searchParams,
}: {
  params: { amt: string };
  searchParams: { [key: string]: string | string[] | undefined };
}) {
  return <SignInForm params={params} searchParams={searchParams} />;
}
