"use client";
// culled from https://github.com/cpvalente/ontime/blob/master/apps/client/src/common/hooks/useLocalStorage.ts

import { useMemo, useRef, useSyncExternalStore } from "react";

const STORAGE_EVENT = "keephq";

function getSnapshot(key: string): string | null {
  // Check if we're in a browser environment
  if (typeof window === "undefined" || typeof localStorage === "undefined") {
    return null;
  }

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
  const localStorageValue = useSyncExternalStore(
    subscribe,
    () => getSnapshot(key),
    () => JSON.stringify(initialValue)
  );
  const initialValueRef = useRef(initialValue);
  initialValueRef.current = initialValue;

  const parsedLocalStorageValue = useMemo(() => getParsedJson(localStorageValue, initialValueRef.current), [localStorageValue]);

  /**
   * @description Set value to local storage
   * @param value
   */
  const setLocalStorageValue = (value: T | ((val: T) => T)) => {
    // Check if we're in a browser environment
    if (typeof window === "undefined" || typeof localStorage === "undefined") {
      return;
    }

    // Allow value to be a function so we have same API as useState
    const valueToStore =
      value instanceof Function ? value(parsedLocalStorageValue) : value;

    try {
      localStorage.setItem(`keephq-${key}`, JSON.stringify(valueToStore));
      window.dispatchEvent(new StorageEvent(STORAGE_EVENT));
    } catch (error) {
      console.warn("Failed to save to localStorage:", error);
    }
  };

  return [parsedLocalStorageValue, setLocalStorageValue] as const;
};

function subscribe(callback: () => void) {
  // Check if we're in a browser environment
  if (typeof window === "undefined") {
    return () => {}; // Return empty cleanup function
  }
  
  window.addEventListener(STORAGE_EVENT, callback);

  return () => {
    window.removeEventListener(STORAGE_EVENT, callback);
  };
}
