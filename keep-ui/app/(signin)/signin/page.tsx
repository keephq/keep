"use client";;
import { use } from "react";
import SignInForm from "./SignInForm";

export default function SignInPage(
  props: {
    params: Promise<{ amt: string }>;
    searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
  }
) {
  const searchParams = use(props.searchParams);
  const params = use(props.params);
  return <SignInForm params={params} searchParams={searchParams} />;
}
