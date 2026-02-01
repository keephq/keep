/**
 * Tremor UI utility constants and functions for consistent styling
 * 
 * These variables and functions help maintain a consistent style across the application
 * by providing reusable Tailwind CSS class collections for common UI states.
 */

// Tremor focusInput [v0.0.1]
/**
 * Tailwind CSS classes for input focus state
 */
export const focusInput = [
  // base
  "focus:ring-2",
  // ring color
  "focus:ring-blue-200 focus:dark:ring-blue-700/30",
  // border color
  "focus:border-blue-500 focus:dark:border-blue-700",
];

// Tremor hasErrorInput [v0.0.1]
/**
 * Tailwind CSS classes for input error state
 */
export const hasErrorInput = [
  // base
  "ring-2",
  // border color
  "border-red-500 dark:border-red-700",
  // ring color
  "ring-red-200 dark:ring-red-700/30",
];

// Tremor focusRing [v0.0.1]
/**
 * Tailwind CSS classes for focus ring effect on interactive elements
 */
export const focusRing = [
  // base
  "outline outline-offset-2 outline-0 focus-visible:outline-2",
  // outline color
  "outline-blue-500 dark:outline-blue-500",
];

import clsx, { type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

// Tremor cx [v0.0.0]
/**
 * Utility function to merge and deduplicate Tailwind CSS classes
 * 
 * @param args - Any number of class values, strings, arrays, or objects
 * @returns A string of merged and deduplicated CSS classes
 * 
 * @example
 * // Merge multiple class sources with proper precedence
 * <div className={cx(
 *   "base-class",
 *   isActive && "active-class",
 *   hasError ? "error-class" : "normal-class"
 * )} />
 */
export function cx(...args: ClassValue[]) {
  return twMerge(clsx(...args));
}
