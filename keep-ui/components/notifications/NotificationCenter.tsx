import { useEffect, useState } from 'react';
import { useApi } from '@/shared/lib/hooks/useApi';
import { useHydratedSession as useSession } from '@/shared/lib/hooks/useHydratedSession';
import { Button, Card, Title, Text, Badge } from '@tremor/react';
import { useRouter } from 'next/navigation';
import { UserStatefulAvatar } from '@/entities/users/ui/UserStatefulAvatar';
import { formatDistanceToNow } from 'date-fns';

interface Notification {
  id: string;
  type: 'mention' | 'alert' | 'system';
  title: string;
  message: string;
  timestamp: string;
  read: boolean;
  sourceId?: string;
  sourceType?: string;
  sourceUrl?: string;
  initiator?: string;
}

export function NotificationCenter() {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const api = useApi();
  const { data: session } = useSession();
  const router = useRouter();

  // Fetch notifications
  const fetchNotifications = async () => {
    try {
      // This would be a real API call in production
      // const response = await api.get('/notifications');
      // setNotifications(response.data);
      
      // For demo purposes, we'll use mock data
      const mockNotifications: Notification[] = [
        {
          id: '1',
          type: 'mention',
          title: 'You were mentioned in a comment',
          message: 'User mentioned you in incident #INC-123',
          timestamp: new Date().toISOString(),
          read: false,
          sourceId: '123',
          sourceType: 'incident',
          sourceUrl: '/incidents/123',
          initiator: 'user@example.com'
        },
        {
          id: '2',
          type: 'alert',
          title: 'New critical alert',
          message: 'A new critical alert was triggered for service X',
          timestamp: new Date(Date.now() - 3600000).toISOString(),
          read: true,
          sourceId: '456',
          sourceType: 'alert',
          sourceUrl: '/alerts?fingerprint=456'
        }
      ];
      
      setNotifications(mockNotifications);
      setUnreadCount(mockNotifications.filter(n => !n.read).length);
    } catch (error) {
      console.error('Failed to fetch notifications', error);
    }
  };

  // Mark notification as read
  const markAsRead = async (id: string) => {
    try {
      // This would be a real API call in production
      // await api.post(`/notifications/${id}/read`);
      
      // For demo purposes, we'll update the state directly
      setNotifications(prev => 
        prev.map(n => n.id === id ? { ...n, read: true } : n)
      );
      setUnreadCount(prev => Math.max(0, prev - 1));
    } catch (error) {
      console.error('Failed to mark notification as read', error);
    }
  };

  // Navigate to the source of the notification
  const navigateToSource = (notification: Notification) => {
    if (notification.sourceUrl) {
      router.push(notification.sourceUrl);
      markAsRead(notification.id);
      setIsOpen(false);
    }
  };

  // Initialize notifications
  useEffect(() => {
    if (session?.user) {
      fetchNotifications();
    }
  }, [session?.user]);

  // Set up real-time updates (would use Pusher in production)
  useEffect(() => {
    // Mock receiving a new notification after 5 seconds
    const timer = setTimeout(() => {
      const newNotification: Notification = {
        id: '3',
        type: 'mention',
        title: 'New mention',
        message: 'Another user mentioned you in a comment',
        timestamp: new Date().toISOString(),
        read: false,
        sourceId: '789',
        sourceType: 'incident',
        sourceUrl: '/incidents/789',
        initiator: 'another@example.com'
      };
      
      setNotifications(prev => [newNotification, ...prev]);
      setUnreadCount(prev => prev + 1);
    }, 5000);
    
    return () => clearTimeout(timer);
  }, []);

  return (
    <div className="relative">
      {/* Notification Bell */}
      <button 
        className="relative p-2 text-gray-600 hover:text-gray-800 focus:outline-none"
        onClick={() => setIsOpen(!isOpen)}
      >
        <svg 
          xmlns="http://www.w3.org/2000/svg" 
          className="h-6 w-6" 
          fill="none" 
          viewBox="0 0 24 24" 
          stroke="currentColor"
        >
          <path 
            strokeLinecap="round" 
            strokeLinejoin="round" 
            strokeWidth={2} 
            d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" 
          />
        </svg>
        
        {/* Unread Badge */}
        {unreadCount > 0 && (
          <span className="absolute top-0 right-0 inline-flex items-center justify-center px-2 py-1 text-xs font-bold leading-none text-white transform translate-x-1/2 -translate-y-1/2 bg-red-500 rounded-full">
            {unreadCount}
          </span>
        )}
      </button>
      
      {/* Notification Panel */}
      {isOpen && (
        <div className="absolute right-0 mt-2 w-80 bg-white rounded-md shadow-lg overflow-hidden z-50">
          <div className="py-2 px-3 bg-gray-100 flex justify-between items-center">
            <Title className="text-sm font-semibold">Notifications</Title>
            {notifications.length > 0 && (
              <Button 
                size="xs" 
                variant="light"
                onClick={() => {
                  // Mark all as read
                  setNotifications(prev => prev.map(n => ({ ...n, read: true })));
                  setUnreadCount(0);
                }}
              >
                Mark all as read
              </Button>
            )}
          </div>
          
          <div className="max-h-96 overflow-y-auto">
            {notifications.length === 0 ? (
              <div className="py-4 px-3 text-center text-gray-500">
                No notifications
              </div>
            ) : (
              notifications.map(notification => (
                <div 
                  key={notification.id}
                  className={`border-b border-gray-100 cursor-pointer ${notification.read ? 'bg-white' : 'bg-blue-50'}`}
                  onClick={() => navigateToSource(notification)}
                >
                  <div className="p-3 hover:bg-gray-50">
                    <div className="flex items-start">
                      {notification.initiator && (
                        <div className="mr-3">
                          <UserStatefulAvatar email={notification.initiator} size="sm" />
                        </div>
                      )}
                      <div className="flex-1">
                        <div className="flex justify-between items-start">
                          <Text className="font-semibold">{notification.title}</Text>
                          <Badge size="xs" color={notification.read ? 'gray' : 'blue'}>
                            {notification.read ? 'Read' : 'New'}
                          </Badge>
                        </div>
                        <Text className="text-sm text-gray-600">{notification.message}</Text>
                        <Text className="text-xs text-gray-400 mt-1">
                          {formatDistanceToNow(new Date(notification.timestamp), { addSuffix: true })}
                        </Text>
                      </div>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
