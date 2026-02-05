export function uuidToArrayItem(uuidString: string, array: any[]): number {
  // Remove hyphens and take the first 8 characters
  const uuidPart = uuidString.replace(/-/g, "").slice(0, 8);

  // Convert to integer and use modulo to get a number between 0 and 21
  return parseInt(uuidPart, 16) % array.length;
}

export function getColorForUUID(id: string) {
  // id is a uuid v4
  const allColors = [
    "red",
    "orange",
    "amber",
    "yellow",
    "lime",
    "green",
    "emerald",
    "teal",
    "cyan",
    "sky",
    "blue",
    "indigo",
    "violet",
    "purple",
    "fuchsia",
    "pink",
    "rose",
  ];
  const index = uuidToArrayItem(id, allColors);
  return allColors[index];
}
