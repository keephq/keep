import { useState, useCallback } from "react";

export interface GroupExpansionState {
  [groupKey: string]: boolean;
}

export function useGroupExpansion(defaultExpanded: boolean = true) {
  const [expandedGroups, setExpandedGroups] = useState<GroupExpansionState>({});
  const [allGroupKeys, setAllGroupKeys] = useState<Set<string>>(new Set());

  const isGroupExpanded = useCallback(
    (groupKey: string) => {
      // If the group key doesn't exist in state, use default value
      return expandedGroups[groupKey] ?? defaultExpanded;
    },
    [expandedGroups, defaultExpanded]
  );

  const toggleGroup = useCallback(
    (groupKey: string) => {
      setExpandedGroups((prev: GroupExpansionState) => ({
        ...prev,
        [groupKey]: !isGroupExpanded(groupKey),
      }));
    },
    [isGroupExpanded]
  );

  const collapseAll = useCallback(() => {
    // Get all current group keys and set them to false
    const allCollapsed: GroupExpansionState = {};
    allGroupKeys.forEach((key: string) => {
      allCollapsed[key] = false;
    });
    setExpandedGroups(allCollapsed);
  }, [allGroupKeys]);

  const expandAll = useCallback(() => {
    // Get all current group keys and set them to true
    const allExpanded: GroupExpansionState = {};
    allGroupKeys.forEach((key: string) => {
      allExpanded[key] = true;
    });
    setExpandedGroups(allExpanded);
  }, [allGroupKeys]);

  const setGroupExpanded = useCallback((groupKey: string, expanded: boolean) => {
    setExpandedGroups((prev: GroupExpansionState) => ({
      ...prev,
      [groupKey]: expanded,
    }));
  }, []);

  // Initialize groups that haven't been seen yet
  const initializeGroup = useCallback(
    (groupKey: string) => {
      // Track all group keys
      setAllGroupKeys((prev: Set<string>) => new Set(prev).add(groupKey));
      
      if (!(groupKey in expandedGroups)) {
        setExpandedGroups((prev: GroupExpansionState) => ({
          ...prev,
          [groupKey]: defaultExpanded,
        }));
      }
    },
    [expandedGroups, defaultExpanded]
  );

  return {
    isGroupExpanded,
    toggleGroup,
    collapseAll,
    expandAll,
    setGroupExpanded,
    initializeGroup,
    expandedGroups,
  };
}