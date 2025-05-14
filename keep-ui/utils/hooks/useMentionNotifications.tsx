import { useEffect, useState } from 'react';
import { useSession } from 'next-auth/react';
import { toast } from 'react-toastify';
import { useRouter } from 'next/navigation';
import { useWebsocket } from './usePusher';

export function useMentionNotifications() {
  const { data: session } = useSession();
  const websocket = useWebsocket();
  const router = useRouter();
  // Add isClient state to prevent hydration mismatch
  const [isClient, setIsClient] = useState(false);

  // Set isClient to true on component mount
  useEffect(() => {
    setIsClient(true);
  }, []);

  useEffect(() => {
    // Only run this effect on the client side
    if (!isClient || !websocket || !session?.user?.email) return;

    // Subscribe to the websocket
    websocket.subscribe();

    // Define the event handler
    const handleMention = (data: {
      incident_id: string;
      mentioned_by: string;
      comment: string;
    }) => {
      // Show a notification with the mention
      toast.info(
        <div>
          <p className="font-bold">You were mentioned in an incident</p>
          <p>By: {data.mentioned_by}</p>
          <p className="truncate max-w-xs">{data.comment}</p>
          <button
            className="bg-blue-500 text-white px-2 py-1 rounded mt-2"
            onClick={() => router.push(`/incidents/${data.incident_id}`)}
          >
            View Incident
          </button>
        </div>,
        {
          position: 'top-right',
          autoClose: 10000, // 10 seconds
          closeOnClick: false,
          pauseOnHover: true,
        }
      );
    };

    // Bind the event handler
    websocket.bind('incident-mention', handleMention);

    // Cleanup on unmount
    return () => {
      websocket.unbind('incident-mention', handleMention);
      websocket.unsubscribe();
    };
  }, [isClient, websocket, session, router]);
}
