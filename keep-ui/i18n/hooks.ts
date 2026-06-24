import { useTranslations } from "next-intl";
import en from "./messages/en/index.json";

type NestedKeyOf<T extends object> = {
  [K in keyof T & string]: T[K] extends object
    ? `${K}` | `${K}.${NestedKeyOf<T[K] & object>}`
    : `${K}`;
}[keyof T & string];

export type TranslationNamespace = keyof typeof en;
export type TranslationKey<N extends TranslationNamespace> = NestedKeyOf<
  (typeof en)[N] & object
>;

export function useAppTranslations<N extends TranslationNamespace>(
  namespace: N
) {
  return useTranslations(namespace);
}
