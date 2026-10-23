import { router, Tabs } from 'expo-router'
import { useShareIntentContext } from 'expo-share-intent'
import { useEffect, type ReactNode } from 'react'
import { Alert, type ColorValue } from 'react-native'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import Svg, { Circle, Path } from 'react-native-svg'

import { inProgress, useRequests, useShareReel } from '@/reels'
import { colors, fonts } from '@/theme'

function Icon({ color, children }: { color: ColorValue; children: ReactNode }) {
  return (
    <Svg
      width={24}
      height={24}
      viewBox="0 0 24 24"
      fill="none"
      stroke={color}
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {children}
    </Svg>
  )
}

export default function TabsLayout() {
  // Design: 62px of content over 22px of bottom padding; system nav buttons get at least that.
  const bottom = Math.max(useSafeAreaInsets().bottom, 22)
  const busy = useRequests().data?.some(inProgress)
  useSharedReels()
  return (
    // History, so back from the movie page returns to the tab it was opened from.
    <Tabs
      backBehavior="history"
      screenOptions={{
        headerShown: false,
        sceneStyle: { backgroundColor: colors.background },
        tabBarActiveTintColor: colors.accent,
        tabBarInactiveTintColor: colors.tabInactive,
        tabBarStyle: {
          backgroundColor: colors.tabBar,
          borderTopColor: colors.tabBarBorder,
          height: 62 + bottom,
          paddingBottom: bottom,
        },
        tabBarLabelStyle: { fontFamily: fonts.semibold, fontSize: 11 },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: 'Search',
          tabBarIcon: ({ color }) => (
            <Icon color={color}>
              <Circle cx={11} cy={11} r={7} />
              <Path d="M20 20l-4-4" />
            </Icon>
          ),
        }}
      />
      <Tabs.Screen
        name="to-watch"
        options={{
          title: 'To watch',
          tabBarIcon: ({ color }) => (
            <Icon color={color}>
              <Path d="M6 4h12v17l-6-4-6 4z" />
            </Icon>
          ),
        }}
      />
      <Tabs.Screen
        name="watched"
        options={{
          title: 'Watched',
          tabBarIcon: ({ color }) => (
            <Icon color={color}>
              <Circle cx={12} cy={12} r={9} />
              <Path d="M8 12.5l2.5 2.5L16 9.5" />
            </Icon>
          ),
        }}
      />
      <Tabs.Screen
        name="favourites"
        options={{
          title: 'Favourites',
          tabBarIcon: ({ color }) => (
            <Icon color={color}>
              <Path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z" />
            </Icon>
          ),
        }}
      />
      <Tabs.Screen
        name="requests"
        options={{
          title: 'Requests',
          // An empty badge is a dot: some reel is still being identified.
          tabBarBadge: busy ? '' : undefined,
          tabBarAccessibilityLabel: busy ? 'Requests, some in progress' : 'Requests',
          tabBarBadgeStyle: { minWidth: 9, maxHeight: 9, borderRadius: 5, backgroundColor: colors.accent },
          tabBarIcon: ({ color }) => (
            <Icon color={color}>
              <Path d="M4 13l2.5-8h11L20 13v6H4z" />
              <Path d="M4 13h4.5l1 2.5h5l1-2.5H20" />
            </Icon>
          ),
        }}
      />
      {/* Inside the tabs, not the root stack, so the tab bar stays visible on it. */}
      <Tabs.Screen name="movie/[tmdbId]" options={{ href: null }} />
    </Tabs>
  )
}

/**
 * Sends a reel shared to the app from Instagram, then shows Requests.
 * Lives here, behind the sign-in guard: a reel shared while signed out waits for sign-in, and is dropped if you leave the app first.
 */
function useSharedReels() {
  const { hasShareIntent, shareIntent, resetShareIntent } = useShareIntentContext()
  const { mutate } = useShareReel()
  useEffect(() => {
    if (!hasShareIntent) return
    const url = shareIntent.webUrl ?? shareIntent.text
    resetShareIntent()
    if (!url) return
    mutate(url, { onError: () => Alert.alert("Couldn't send the reel", 'Only Instagram reels and posts can be shared.') })
    router.navigate('/requests')
  }, [hasShareIntent, shareIntent, resetShareIntent, mutate])
}
