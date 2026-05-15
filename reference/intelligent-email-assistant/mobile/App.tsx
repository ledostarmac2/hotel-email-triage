import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { Ionicons } from '@expo/vector-icons';
import { Provider } from 'react-redux';
import { store } from './src/store';

// Import screens
import DashboardScreen from './src/screens/DashboardScreen';
import EmailsScreen from './src/screens/EmailsScreen';
import SettingsScreen from './src/screens/SettingsScreen';
import NotificationsScreen from './src/screens/NotificationsScreen';

const Tab = createBottomTabNavigator();

export default function App(): React.ReactElement {
  return (
    <Provider store={store}>
      <SafeAreaProvider>
        <NavigationContainer>
          <StatusBar style="auto" />
          <Tab.Navigator
            screenOptions={({ route }) => ({
              tabBarIcon: ({ focused, color, size }) => {
                let iconName: keyof typeof Ionicons.glyphMap;

                if (route.name === 'Dashboard') {
                  iconName = focused ? 'analytics' : 'analytics-outline';
                } else if (route.name === 'Emails') {
                  iconName = focused ? 'mail' : 'mail-outline';
                } else if (route.name === 'Notifications') {
                  iconName = focused ? 'notifications' : 'notifications-outline';
                } else if (route.name === 'Settings') {
                  iconName = focused ? 'settings' : 'settings-outline';
                } else {
                  iconName = 'help-outline';
                }

                return <Ionicons name={iconName} size={size} color={color} />;
              },
              tabBarActiveTintColor: '#2196F3',
              tabBarInactiveTintColor: 'gray',
              headerStyle: {
                backgroundColor: '#2196F3',
              },
              headerTintColor: '#fff',
              headerTitleStyle: {
                fontWeight: 'bold',
              },
            })}
          >
            <Tab.Screen 
              name="Dashboard" 
              component={DashboardScreen}
              options={{
                title: 'Dashboard',
                headerTitle: 'Email Assistant'
              }}
            />
            <Tab.Screen 
              name="Emails" 
              component={EmailsScreen}
              options={{
                title: 'Emails',
                headerTitle: 'Processed Emails'
              }}
            />
            <Tab.Screen 
              name="Notifications" 
              component={NotificationsScreen}
              options={{
                title: 'Notifications',
                headerTitle: 'WhatsApp Alerts'
              }}
            />
            <Tab.Screen 
              name="Settings" 
              component={SettingsScreen}
              options={{
                title: 'Settings',
                headerTitle: 'App Settings'
              }}
            />
          </Tab.Navigator>
        </NavigationContainer>
      </SafeAreaProvider>
    </Provider>
  );
}
