"use client";

import { useEffect, useState } from "react";
import { ChevronLeftIcon, ChevronRightIcon } from "@heroicons/react/24/outline";

export const MinimizeMenuButton = () => {
  const [isMinimized, setIsMinimized] = useState(false);

  // Initialize state from localStorage on mount
  useEffect(() => {
    if (typeof window !== "undefined") {
      const storedState = localStorage.getItem("sidebar-minimized") === "true";
      setIsMinimized(storedState);
    }
  }, []);

  // Listen for external changes to the minimized state
  useEffect(() => {
    const handleStorageChange = (e) => {
      if (e.key === "sidebar-minimized") {
        setIsMinimized(e.newValue === "true");
      }
    };

    const handleCustomEvent = (e) => {
      if (e.detail && e.detail.key === "sidebar-minimized") {
        setIsMinimized(e.detail.value === "true");
      }
    };

    window.addEventListener("storage", handleStorageChange);
    window.addEventListener("sidebarStateChange", handleCustomEvent);

    return () => {
      window.removeEventListener("storage", handleStorageChange);
      window.removeEventListener("sidebarStateChange", handleCustomEvent);
    };
  }, []);

  // Toggle minimized state
  const toggleMinimized = () => {
    const newState = !isMinimized;
    setIsMinimized(newState);

    // Save to localStorage
    localStorage.setItem("sidebar-minimized", String(newState));

    // Dispatch a custom event for other components to listen to
    window.dispatchEvent(
      new CustomEvent("sidebarStateChange", {
        detail: { key: "sidebar-minimized", value: String(newState) },
      })
    );
  };

  return (
    <button
      className="minimize-button"
      onClick={toggleMinimized}
      aria-label={isMinimized ? "Expand sidebar" : "Collapse sidebar"}
      title={isMinimized ? "Expand sidebar" : "Collapse sidebar"}
    >
      {isMinimized ? (
        <ChevronRightIcon className="h-4 w-4" />
      ) : (
        <ChevronLeftIcon className="h-4 w-4" />
      )}
    </button>
  );
};
