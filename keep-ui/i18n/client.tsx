"use client";

import { NextIntlClientProvider } from "next-intl";
import { ReactNode } from "react";

interface IntlProviderProps {
  children: ReactNode;
  messages: Record<string, any>;
  locale: string;
}

export function IntlProvider({ children, messages, locale }: IntlProviderProps) {
  return (
    <NextIntlClientProvider messages={messages} locale={locale}>
      {children}
    </NextIntlClientProvider>
  );
}
