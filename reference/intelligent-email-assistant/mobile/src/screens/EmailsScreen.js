import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  RefreshControl,
  TouchableOpacity,
  Alert,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import ApiService from '../services/ApiService';

export default function EmailsScreen() {
  const [emails, setEmails] = useState([]);
  const [loading, setLoading] = useState(false);

  const loadEmails = async () => {
    setLoading(true);
    try {
      const response = await ApiService.getEmails();
      setEmails(response.data || []);
    } catch (error) {
      Alert.alert('Error', 'Failed to load emails');
      console.error('Error loading emails:', error);
      // Show mock data if API fails
      setEmails([
        {
          id: '1',
          subject: 'Meeting Request - Project Review',
          senderName: 'John Doe',
          senderEmail: 'john@company.com',
          receivedTime: '2025-01-01T10:30:00',
          needsAttention: true,
          responseGenerated: false,
          analysis: 'This email requires personal attention as it involves scheduling.'
        },
        {
          id: '2', 
          subject: 'Newsletter Subscription Confirmation',
          senderName: 'Newsletter Team',
          senderEmail: 'noreply@newsletter.com',
          receivedTime: '2025-01-01T09:15:00',
          needsAttention: false,
          responseGenerated: true,
          analysis: 'Routine confirmation email - auto-response sent.'
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadEmails();
  }, []);

  const formatTime = (timeString) => {
    return new Date(timeString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const renderEmailItem = ({ item }) => (
    <TouchableOpacity style={styles.emailCard}>
      <View style={styles.emailHeader}>
        <View style={styles.emailMeta}>
          <Text style={styles.senderName}>{item.senderName}</Text>
          <Text style={styles.senderEmail}>{item.senderEmail}</Text>
        </View>
        <View style={styles.statusContainer}>
          {item.needsAttention ? (
            <View style={styles.attentionBadge}>
              <Ionicons name="alert-circle" size={16} color="#FF9800" />
              <Text style={styles.attentionText}>Attention</Text>
            </View>
          ) : (
            <View style={styles.processedBadge}>
              <Ionicons name="checkmark-circle" size={16} color="#4CAF50" />
              <Text style={styles.processedText}>Processed</Text>
            </View>
          )}
        </View>
      </View>
      
      <Text style={styles.subject}>{item.subject}</Text>
      <Text style={styles.analysis}>{item.analysis}</Text>
      
      <View style={styles.emailFooter}>
        <Text style={styles.timestamp}>
          {formatTime(item.receivedTime)}
        </Text>
        {item.responseGenerated && (
          <View style={styles.responseBadge}>
            <Ionicons name="send" size={14} color="#9C27B0" />
            <Text style={styles.responseText}>Auto-responded</Text>
          </View>
        )}
      </View>
    </TouchableOpacity>
  );

  return (
    <View style={styles.container}>
      {emails.length === 0 && !loading ? (
        <View style={styles.emptyState}>
          <Ionicons name="mail-outline" size={64} color="#ccc" />
          <Text style={styles.emptyText}>No emails processed yet</Text>
          <Text style={styles.emptySubtext}>
            Emails will appear here once they are processed by the AI assistant
          </Text>
        </View>
      ) : (
        <FlatList
          data={emails}
          keyExtractor={(item) => item.id}
          renderItem={renderEmailItem}
          refreshControl={
            <RefreshControl refreshing={loading} onRefresh={loadEmails} />
          }
          contentContainerStyle={styles.listContainer}
          showsVerticalScrollIndicator={false}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  listContainer: {
    padding: 16,
  },
  emailCard: {
    backgroundColor: 'white',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 3,
    elevation: 3,
  },
  emailHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 8,
  },
  emailMeta: {
    flex: 1,
  },
  senderName: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#333',
  },
  senderEmail: {
    fontSize: 12,
    color: '#666',
    marginTop: 2,
  },
  statusContainer: {
    alignItems: 'flex-end',
  },
  attentionBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFF3E0',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 12,
  },
  attentionText: {
    fontSize: 12,
    color: '#FF9800',
    marginLeft: 4,
    fontWeight: '600',
  },
  processedBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#E8F5E8',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 12,
  },
  processedText: {
    fontSize: 12,
    color: '#4CAF50',
    marginLeft: 4,
    fontWeight: '600',
  },
  subject: {
    fontSize: 14,
    fontWeight: '600',
    color: '#333',
    marginBottom: 8,
    lineHeight: 20,
  },
  analysis: {
    fontSize: 13,
    color: '#666',
    lineHeight: 18,
    marginBottom: 12,
  },
  emailFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  timestamp: {
    fontSize: 12,
    color: '#999',
  },
  responseBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#F3E5F5',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 12,
  },
  responseText: {
    fontSize: 11,
    color: '#9C27B0',
    marginLeft: 4,
    fontWeight: '600',
  },
  emptyState: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 40,
  },
  emptyText: {
    fontSize: 18,
    color: '#666',
    marginTop: 16,
    fontWeight: '600',
  },
  emptySubtext: {
    fontSize: 14,
    color: '#999',
    textAlign: 'center',
    marginTop: 8,
    lineHeight: 20,
  },
});
