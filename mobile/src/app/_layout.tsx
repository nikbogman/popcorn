import { Fraunces_600SemiBold } from '@expo-google-fonts/fraunces/600SemiBold'
import { InstrumentSans_400Regular } from '@expo-google-fonts/instrument-sans/400Regular'
import { InstrumentSans_500Medium } from '@expo-google-fonts/instrument-sans/500Medium'
import { InstrumentSans_600SemiBold } from '@expo-google-fonts/instrument-sans/600SemiBold'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useFonts } from 'expo-font'
import { Stack } from 'expo-router'
import * as SplashScreen from 'expo-splash-screen'
import { ShareIntentProvider } from 'expo-share-intent'
import { StatusBar } from 'expo-status-bar'
import { useEffect } from 'react'

import { useToken } from '@/auth'
import { colors } from '@/theme'

SplashScreen.preventAutoHideAsync()

const queryClient = new QueryClient()

export default function RootLayout() {
  const [fontsLoaded, fontError] = useFonts({
    Fraunces_600SemiBold,
    InstrumentSans_400Regular,
    InstrumentSans_500Medium,
    InstrumentSans_600SemiBold,
  })
  const token = useToken()
  const ready = (fontsLoaded || !!fontError) && token !== undefined

  useEffect(() => {
    if (ready) SplashScreen.hideAsync()
  }, [ready])

  if (!ready) return null

  return (
    <ShareIntentProvider>
      <QueryClientProvider client={queryClient}>
        <StatusBar style="light" />
        <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: colors.background } }}>
          <Stack.Protected guard={!!token}>
            <Stack.Screen name="(tabs)" />
          </Stack.Protected>
          <Stack.Protected guard={!token}>
            <Stack.Screen name="login" />
          </Stack.Protected>
        </Stack>
      </QueryClientProvider>
    </ShareIntentProvider>
  )
}
