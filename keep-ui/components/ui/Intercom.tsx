"use client";

import Script from "next/script";

export function updateIntercom(user: any) {
  if (user !== undefined) {
    try {
      (window as any)?.Intercom("update", {
        ...user,
      });
    } catch (e) {}
  }
}

export function hideOrShowIntercom(hide: boolean = true) {
  try {
    (window as any)?.Intercom("update", {
      hide_default_launcher: hide,
    });
  } catch (e) {}
}

export function shutdownIntercom() {
  try {
    (window as any)?.Intercom("shutdown");
  } catch (e) {}
}

function onLoad() {
  (window as any)?.Intercom("boot", {
    api_base: "https://api-iam.intercom.io",
    app_id: "dio2er83",
  });
}

export const Intercom = () => {
  return (
    <Script
      id="intercom"
      onLoad={onLoad}
      strategy="lazyOnload"
      src="https://widget.intercom.io/widget/dio2er83"
    ></Script>
  );
};
