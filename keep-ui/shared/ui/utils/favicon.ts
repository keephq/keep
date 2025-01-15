export function setFavicon(status: string) {
  const favicon: HTMLLinkElement | null =
    document.querySelector('link[rel="icon"]');
  if (!favicon) {
    return;
  }

  switch (status) {
    case "success":
      favicon.href = "/keep-success.png";
      break;
    case "failure":
      favicon.href = "/keep-failure.png";
      break;
    case "pending":
      favicon.href = "/keep-pending.png";
      break;
    default:
      favicon.href = "/favicon.ico";
  }
}
