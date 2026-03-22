"use client";

import { useTransition } from "react";
import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { Menu, Transition } from "@headlessui/react";
import { GlobeIcon } from "lucide-react";
import {
  locales,
  localeNames,
  localeCookieName,
  type Locale,
} from "@/i18n/config";
import clsx from "clsx";

export function LanguageSwitcher() {
  const locale = useLocale();
  const t = useTranslations("common.language");
  const router = useRouter();
  const [isPending, startTransition] = useTransition();

  const handleLocaleChange = (newLocale: Locale) => {
    if (newLocale === locale) return;

    // 设置 cookie
    document.cookie = `${localeCookieName}=${newLocale};path=/;max-age=31536000`;

    // 刷新页面以应用新语言
    startTransition(() => {
      router.refresh();
    });
  };

  return (
    <Menu as="div" className="relative">
      <Menu.Button
        className="h-9 w-auto gap-1 border-none bg-transparent px-2 shadow-none flex items-center text-sm text-gray-700 hover:text-orange-500 rounded-lg hover:bg-stone-200/50 transition-colors"
        aria-label={t("title")}
        disabled={isPending}
      >
        <GlobeIcon className="h-4 w-4" />
        <span className="text-xs">{localeNames[locale as Locale]}</span>
      </Menu.Button>
      <Transition
        enter="transition ease-out duration-100"
        enterFrom="transform opacity-0 scale-95"
        enterTo="transform opacity-100 scale-100"
        leave="transition ease-in duration-75"
        leaveFrom="transform opacity-100 scale-100"
        leaveTo="transform opacity-0 scale-95"
      >
        <Menu.Items className="absolute right-0 bottom-full mb-1 w-32 origin-bottom-right divide-y divide-gray-100 rounded-md bg-white shadow-lg ring-1 ring-black/5 focus:outline-none z-50">
          <div className="px-1 py-1">
            {locales.map((loc) => (
              <Menu.Item key={loc}>
                {({ active }) => (
                  <button
                    type="button"
                    onClick={() => handleLocaleChange(loc)}
                    className={clsx(
                      "group flex w-full items-center rounded-md px-2 py-2 text-sm",
                      active ? "bg-orange-400 text-white" : "text-gray-900",
                      locale === loc && "font-semibold"
                    )}
                  >
                    {localeNames[loc]}
                  </button>
                )}
              </Menu.Item>
            ))}
          </div>
        </Menu.Items>
      </Transition>
    </Menu>
  );
}
