// culled from https://github.com/cpvalente/ontime/blob/master/apps/client/src/common/hooks/useLocalStorage.ts

import { useSyncExternalStore } from "react";

const STORAGE_EVENT = "keephq";

function getSnapshot(key: string): string | null {
  try {
    return localStorage.getItem(`keephq-${key}`);
  } catch {
    return null;
  }
}

function getParsedJson<T>(
  localStorageValue: string | null,
  initialValue: T
): T {
  try {
    return localStorageValue ? JSON.parse(localStorageValue) : initialValue;
  } catch {
    return initialValue;
  }
}

export const useLocalStorage = <T>(key: string, initialValue: T) => {
  const localStorageValue = useSyncExternalStore(subscribe, () =>
    getSnapshot(key)
  );
  const parsedLocalStorageValue = getParsedJson(
    localStorageValue,
    initialValue
  );

  /**
   * @description Set value to local storage
   * @param value
   */
  const setLocalStorageValue = (value: T | ((val: T) => T)) => {
    // Allow value to be a function so we have same API as useState
    const valueToStore =
      value instanceof Function ? value(parsedLocalStorageValue) : value;

    localStorage.setItem(`keephq-${key}`, JSON.stringify(valueToStore));
    window.dispatchEvent(new StorageEvent(STORAGE_EVENT));
  };

  return [parsedLocalStorageValue, setLocalStorageValue] as const;
};

function subscribe(callback: () => void) {
  window.addEventListener(STORAGE_EVENT, callback);

  return () => {
    window.removeEventListener(STORAGE_EVENT, callback);
  };
}
