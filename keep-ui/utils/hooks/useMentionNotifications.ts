import { useEffect } from 'react';
import { useSession } from 'next-auth/react';
import { toast } from 'react-toastify';
import { useRouter } from 'next/navigation';
import { usePusher } from './usePusher';

export function useMentionNotifications() {
  const { data: session } = useSession();
  const pusher = usePusher();
  const router = useRouter();

  useEffect(() => {
    if (!pusher || !session?.user?.email) return;

    const tenantId = session.user.tenantId;
    const userEmail = session.user.email;
    const channelName = `private-${tenantId}-${userEmail}`;

    // Subscribe to the user's personal channel for mentions
    const channel = pusher.subscribe(channelName);

    // Listen for mention events
    channel.bind('incident-mention', (data: {
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
    });

    // Cleanup on unmount
    return () => {
      channel.unbind('incident-mention');
      pusher.unsubscribe(channelName);
    };
  }, [pusher, session, router]);
}
