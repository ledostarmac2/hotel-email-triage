import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Switch,
  Alert,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';

export default function SettingsScreen() {
  const [pushNotifications, setPushNotifications] = React.useState(true);
  const [whatsappNotifications, setWhatsappNotifications] = React.useState(true);
  const [autoResponses, setAutoResponses] = React.useState(true);

  const handleAbout = () => {
    Alert.alert(
      'About Intelligent Email Assistant',
      'Version 1.0.0\n\nAn AI-powered email management system that processes your emails intelligently and notifies you when attention is needed.\n\nBuilt with React Native and Spring Boot.',
      [{ text: 'OK' }]
    );
  };

  const SettingItem = ({ icon, title, subtitle, onPress, rightComponent }) => (
    <TouchableOpacity style={styles.settingItem} onPress={onPress}>
      <View style={styles.settingLeft}>
        <Ionicons name={icon} size={24} color="#2196F3" />
        <View style={styles.settingText}>
          <Text style={styles.settingTitle}>{title}</Text>
          {subtitle && <Text style={styles.settingSubtitle}>{subtitle}</Text>}
        </View>
      </View>
      {rightComponent || <Ionicons name="chevron-forward" size={20} color="#ccc" />}
    </TouchableOpacity>
  );

  return (
    <ScrollView style={styles.container}>
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Notifications</Text>
        
        <SettingItem
          icon="notifications"
          title="Push Notifications"
          subtitle="Receive mobile notifications"
          rightComponent={
            <Switch
              value={pushNotifications}
              onValueChange={setPushNotifications}
              trackColor={{ false: '#ccc', true: '#2196F3' }}
            />
          }
        />
        
        <SettingItem
          icon="logo-whatsapp"
          title="WhatsApp Notifications"
          subtitle="Get important email alerts on WhatsApp"
          rightComponent={
            <Switch
              value={whatsappNotifications}
              onValueChange={setWhatsappNotifications}
              trackColor={{ false: '#ccc', true: '#2196F3' }}
            />
          }
        />
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Email Processing</Text>
        
        <SettingItem
          icon="send"
          title="Auto-Responses"
          subtitle="Let AI automatically respond to routine emails"
          rightComponent={
            <Switch
              value={autoResponses}
              onValueChange={setAutoResponses}
              trackColor={{ false: '#ccc', true: '#2196F3' }}
            />
          }
        />
        
        <SettingItem
          icon="time"
          title="Processing Schedule"
          subtitle="Every 5 minutes"
          onPress={() => Alert.alert('Coming Soon', 'Custom scheduling will be available in a future update.')}
        />
        
        <SettingItem
          icon="brain"
          title="AI Provider"
          subtitle="DeepSeek (with OpenAI fallback)"
          onPress={() => Alert.alert('AI Provider', 'Currently using DeepSeek as the primary AI provider with OpenAI as fallback.')}
        />
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Account</Text>
        
        <SettingItem
          icon="person"
          title="User Profile"
          subtitle="Manage your account settings"
          onPress={() => Alert.alert('Coming Soon', 'User profile management will be available soon.')}
        />
        
        <SettingItem
          icon="mail"
          title="Connected Email"
          subtitle="Microsoft 365 account"
          onPress={() => Alert.alert('Email Account', 'Your Microsoft 365 account is connected and active.')}
        />
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Support</Text>
        
        <SettingItem
          icon="help-circle"
          title="Help & FAQ"
          subtitle="Get help with common questions"
          onPress={() => Alert.alert('Help', 'For support, please check the documentation or contact support.')}
        />
        
        <SettingItem
          icon="information-circle"
          title="About"
          subtitle="App version and information"
          onPress={handleAbout}
        />
        
        <SettingItem
          icon="shield-checkmark"
          title="Privacy Policy"
          subtitle="How we protect your data"
          onPress={() => Alert.alert('Privacy Policy', 'Your data is encrypted and processed securely. We never store your email content permanently.')}
        />
      </View>

      <View style={styles.footer}>
        <Text style={styles.footerText}>
          Intelligent Email Assistant v1.0.0
        </Text>
        <Text style={styles.footerSubtext}>
          Making email management smarter
        </Text>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  section: {
    marginVertical: 10,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
    paddingHorizontal: 20,
    paddingVertical: 15,
    backgroundColor: '#f5f5f5',
  },
  settingItem: {
    backgroundColor: 'white',
    paddingHorizontal: 20,
    paddingVertical: 15,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    borderBottomWidth: 1,
    borderBottomColor: '#f0f0f0',
  },
  settingLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
  },
  settingText: {
    marginLeft: 15,
    flex: 1,
  },
  settingTitle: {
    fontSize: 16,
    color: '#333',
    marginBottom: 2,
  },
  settingSubtitle: {
    fontSize: 12,
    color: '#666',
  },
  footer: {
    alignItems: 'center',
    paddingVertical: 30,
    paddingHorizontal: 20,
  },
  footerText: {
    fontSize: 14,
    color: '#666',
    fontWeight: '600',
  },
  footerSubtext: {
    fontSize: 12,
    color: '#999',
    marginTop: 5,
  },
});
