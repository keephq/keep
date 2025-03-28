"use client";

import { useCallback, useEffect, useState } from "react";
import { ChevronLeftIcon, ChevronRightIcon } from "@heroicons/react/24/outline";

export const MinimizeMenuButton = () => {
  const [isMinimized, setIsMinimized] = useState(false);

  // Function to read the minimized state from localStorage
  const readMinimizedState = useCallback(() => {
    if (typeof window !== "undefined") {
      const storedState = localStorage.getItem("sidebar-minimized");
      return storedState === "true";
    }
    return false;
  }, []);

  // Initialize state from localStorage on mount
  useEffect(() => {
    const minimizedState = readMinimizedState();
    setIsMinimized(minimizedState);

    // Apply the minimized state to the document
    if (minimizedState) {
      document.body.setAttribute("data-minimized", "true");
    } else {
      document.body.removeAttribute("data-minimized");
    }
  }, [readMinimizedState]);

  // Toggle minimized state
  const toggleMinimized = () => {
    const newState = !isMinimized;
    setIsMinimized(newState);

    // Save to localStorage
    localStorage.setItem("sidebar-minimized", String(newState));

    // Apply to document
    if (newState) {
      document.body.setAttribute("data-minimized", "true");
    } else {
      document.body.removeAttribute("data-minimized");
    }
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
