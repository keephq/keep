/**
 * Smart ticket link component that renders a clickable link with ticket ID
 */

import { ArrowTopRightOnSquareIcon } from "@heroicons/react/24/outline";

interface TicketLinkProps {
  url?: string;
  id?: string;
  className?: string;
}

/**
 * Extract ticket ID from URL by taking the last segment of the path
 */
function extractTicketId(url: string): string | null {
  try {
    const urlObj = new URL(url);
    const pathSegments = urlObj.pathname.split('/').filter(segment => segment.length > 0);
    
    if (pathSegments.length === 0) return null;
    
    // Get the last segment of the path
    const lastSegment = pathSegments[pathSegments.length - 1];
    
    // Return the last segment if it's not empty
    return lastSegment || null;
  } catch {
    return null;
  }
}

export function TicketLink({ url, id, className }: TicketLinkProps) {
  if (!url || typeof url !== 'string' || !url.startsWith('http')) {
    return <></>;
  }

  const displayId = id || extractTicketId(url);
  
  if (!displayId) {
    return <></>;
  }
  
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className={`inline-flex items-center gap-1 text-blue-600 hover:text-blue-800 text-sm font-medium ${className || ''}`}
      title={`Open ${displayId} in new tab`}
    >
      {displayId}
      <ArrowTopRightOnSquareIcon className="h-3 w-3" />
    </a>
  );
}