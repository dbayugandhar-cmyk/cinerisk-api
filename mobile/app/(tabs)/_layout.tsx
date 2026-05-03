import { Tabs } from 'expo-router';
import React from 'react';
import { HapticTab } from '@/components/haptic-tab';
import { Text } from 'react-native';

export default function TabLayout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarButton: HapticTab,
        tabBarStyle: {
          backgroundColor: '#06080b',
          borderTopColor: 'rgba(255,255,255,0.08)',
          borderTopWidth: 1,
          paddingBottom: 8,
          height: 70,
        },
        tabBarActiveTintColor: '#ff3a3a',
        tabBarInactiveTintColor: 'rgba(255,255,255,0.35)',
        tabBarLabelStyle: {
          fontFamily: 'SpaceMono',
          fontSize: 9,
          letterSpacing: 1.5,
          textTransform: 'uppercase',
          marginTop: 2,
        },
      }}>
      <Tabs.Screen name="index" options={{ title: 'Report', tabBarIcon: ({ color }) => <Text style={{ fontSize: 22, opacity: color === '#ff3a3a' ? 1 : 0.5 }}>🚨</Text> }} />
      <Tabs.Screen name="live" options={{ title: 'Live', tabBarIcon: ({ color }) => <Text style={{ fontSize: 22, opacity: color === '#ff3a3a' ? 1 : 0.5 }}>📡</Text> }} />
      <Tabs.Screen name="stats" options={{ title: 'Stats', tabBarIcon: ({ color }) => <Text style={{ fontSize: 22, opacity: color === '#ff3a3a' ? 1 : 0.5 }}>📊</Text> }} />
    </Tabs>
  );
}
