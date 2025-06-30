// Utility function to migrate column configurations when preset names change
export const migrateColumnConfigurations = (oldPresetName: string, newPresetName: string) => {
  if (oldPresetName === newPresetName) return;
  
  // Skip migration if we're in server-side environment
  if (typeof window === 'undefined') return;
  
  const configKeys = [
    'column-visibility',
    'column-order', 
    'column-rename-mapping',
    'column-time-formats',
    'column-list-formats'
  ];
  
  configKeys.forEach(configType => {
    const oldKey = `${configType}-${oldPresetName}`;
    const newKey = `${configType}-${newPresetName}`;
    
    const oldValue = localStorage.getItem(oldKey);
    if (oldValue && !localStorage.getItem(newKey)) {
      // Only migrate if new key doesn't exist and old key has data
      localStorage.setItem(newKey, oldValue);
      // Clean up old key
      localStorage.removeItem(oldKey);
      console.log(`Migrated column config: ${oldKey} -> ${newKey}`);
    }
  });
};

// Function to clean up orphaned column configurations
export const cleanupOrphanedColumnConfigs = (activePresetNames: string[]) => {
  if (typeof window === 'undefined') return;
  
  const configKeys = [
    'column-visibility',
    'column-order', 
    'column-rename-mapping',
    'column-time-formats',
    'column-list-formats'
  ];
  
  // Get all localStorage keys
  const allKeys = Object.keys(localStorage);
  
  configKeys.forEach(configType => {
    const configKeysToCheck = allKeys.filter(key => key.startsWith(`${configType}-`));
    
    configKeysToCheck.forEach(key => {
      const presetName = key.replace(`${configType}-`, '');
      if (!activePresetNames.includes(presetName)) {
        localStorage.removeItem(key);
        console.log(`Cleaned up orphaned config: ${key}`);
      }
    });
  });
};