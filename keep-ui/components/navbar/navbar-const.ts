export function extendCelWithDefaultFilter(inputCel: string) {
  const celList = ["status == 'firing'", inputCel || ""];
  return celList.join(" && ");
}
