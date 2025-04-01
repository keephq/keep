import { useEffect, useState } from "react";

export function useIsShiftKeyHeld() {
  const [isShiftPressed, setIsShiftPressed] = useState(false);

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Shift") {
        setIsShiftPressed(true);
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [setIsShiftPressed]);

  useEffect(() => {
    function handleKeyUp(e: KeyboardEvent) {
      if (e.key === "Shift") {
        setIsShiftPressed(false);
      }
    }

    document.addEventListener("keyup", handleKeyUp);
    return () => document.removeEventListener("keyup", handleKeyUp);
  }, [setIsShiftPressed]);

  return isShiftPressed;
}
