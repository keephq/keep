"use client";
import SignInForm from "./SignInForm";

export default function SignInPage({ params }: { params: { amt: string } }) {
  return <SignInForm params={params} />;
}
