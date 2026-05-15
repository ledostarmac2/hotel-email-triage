import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  RefreshControl,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';

export default function NotificationsScreen() {
  const [notifications, setNotifications] = React.useState([
    {
      id: '1',
      type: 'urgent',
      title: 'Urgent Email from CEO',
      message: 'Important meeting scheduled for tomorrow at 9 AM',
      time: '2 mins ago',
      read: false,
      icon: 'alert-circle',
      color: '#ff4444',
    },
    {
      id: '2',
      type: 'auto_response',
      title: 'Auto-response sent',
      message: 'Replied to customer support inquiry automatically',
      time: '15 mins ago',
      read: false,
      icon: 'send',
      color: '#4CAF50',
    },
    {
      id: '3',
      type: 'processing',
      title: 'Email batch processed',
      message: '23 emails processed, 2 require attention',
      time: '1 hour ago',
      read: true,
      icon: 'checkmark-circle',
      color: '#2196F3',
    },
    {
      id: '4',
      type: 'whatsapp',
      title: 'WhatsApp notification sent',
      message: 'Priority email alert sent to your WhatsApp',
      time: '2 hours ago',
      read: true,
      icon: 'logo-whatsapp',
      color: '#25D366',
    },
    {
      id: '5',
      type: 'error',
      title: 'Processing error',
      message: 'Failed to process 1 email - authentication issue',
      time: '3 hours ago',
      read: true,
      icon: 'warning',
      color: '#FF9800',
    },
  ]);
  
  const [refreshing, setRefreshing] = React.useState(false);

  const onRefresh = React.useCallback(() => {
    setRefreshing(true);
    
    // Simulate API call
    setTimeout(() => {
      // In a real app, you would fetch new notifications here
      setRefreshing(false);
    }, 1000);
  }, []);

  const markAsRead = (notificationId) => {
    setNotifications(notifications.map(notification =>
      notification.id === notificationId
        ? { ...notification, read: true }
        : notification
    ));
  };

  const clearAllNotifications = () => {
    setNotifications([]);
  };

  const renderNotificationItem = ({ item }) => (
    <TouchableOpacity
      style={[styles.notificationItem, !item.read && styles.unreadItem]}
      onPress={() => markAsRead(item.id)}
    >
      <View style={styles.notificationIcon}>
        <Ionicons name={item.icon} size={24} color={item.color} />
      </View>
      
      <View style={styles.notificationContent}>
        <View style={styles.notificationHeader}>
          <Text style={[styles.notificationTitle, !item.read && styles.unreadText]}>
            {item.title}
          </Text>
          <Text style={styles.notificationTime}>{item.time}</Text>
        </View>
        
        <Text style={styles.notificationMessage}>{item.message}</Text>
        
        {!item.read && <View style={styles.unreadDot} />}
      </View>
    </TouchableOpacity>
  );

  const EmptyState = () => (
    <View style={styles.emptyState}>
      <Ionicons name="notifications-off" size={64} color="#ccc" />
      <Text style={styles.emptyStateText}>No notifications</Text>
      <Text style={styles.emptyStateSubtext}>
        You'll receive notifications here when emails are processed or require attention
      </Text>
    </View>
  );

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Notifications</Text>
        {notifications.length > 0 && (
          <TouchableOpacity onPress={clearAllNotifications} style={styles.clearButton}>
            <Text style={styles.clearButtonText}>Clear All</Text>
          </TouchableOpacity>
        )}
      </View>

      <FlatList
        data={notifications}
        renderItem={renderNotificationItem}
        keyExtractor={(item) => item.id}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            colors={['#2196F3']}
            tintColor="#2196F3"
          />
        }
        ListEmptyComponent={EmptyState}
        contentContainerStyle={notifications.length === 0 ? styles.emptyContainer : {}}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingVertical: 15,
    backgroundColor: 'white',
    borderBottomWidth: 1,
    borderBottomColor: '#f0f0f0',
  },
  headerTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#333',
  },
  clearButton: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 6,
    backgroundColor: '#f0f0f0',
  },
  clearButtonText: {
    fontSize: 14,
    color: '#666',
  },
  notificationItem: {
    backgroundColor: 'white',
    paddingHorizontal: 20,
    paddingVertical: 15,
    flexDirection: 'row',
    alignItems: 'flex-start',
    borderBottomWidth: 1,
    borderBottomColor: '#f0f0f0',
  },
  unreadItem: {
    backgroundColor: '#f8f9ff',
  },
  notificationIcon: {
    marginRight: 15,
    paddingTop: 2,
  },
  notificationContent: {
    flex: 1,
    position: 'relative',
  },
  notificationHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 5,
  },
  notificationTitle: {
    fontSize: 16,
    color: '#333',
    flex: 1,
    marginRight: 10,
  },
  unreadText: {
    fontWeight: '600',
  },
  notificationTime: {
    fontSize: 12,
    color: '#999',
  },
  notificationMessage: {
    fontSize: 14,
    color: '#666',
    lineHeight: 20,
  },
  unreadDot: {
    position: 'absolute',
    top: 2,
    right: 0,
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#2196F3',
  },
  emptyContainer: {
    flex: 1,
  },
  emptyState: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 40,
  },
  emptyStateText: {
    fontSize: 18,
    fontWeight: '600',
    color: '#666',
    marginTop: 20,
    marginBottom: 10,
  },
  emptyStateSubtext: {
    fontSize: 14,
    color: '#999',
    textAlign: 'center',
    lineHeight: 20,
  },
});
