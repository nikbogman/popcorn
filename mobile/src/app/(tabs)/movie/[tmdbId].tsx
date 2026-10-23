import type { ReactNode } from 'react'
import { router, useLocalSearchParams } from 'expo-router'
import { ActivityIndicator, Alert, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import Svg, { Circle, Path } from 'react-native-svg'

import { useMovie, useSetEntry, type Status } from '@/collection'
import { Poster } from '@/components/movie-row'
import { colors, fonts } from '@/theme'

export default function Movie() {
  const { tmdbId } = useLocalSearchParams<{ tmdbId: string }>()
  const { top } = useSafeAreaInsets()
  const movie = useMovie(tmdbId)
  // One mutation for all three buttons, so they're all disabled while any toggle is saving.
  const toggle = useSetEntry(tmdbId, { onError: () => Alert.alert("Couldn't save", 'Nothing was changed. Try again in a moment.') })
  // Pressing the button that's on clears it: the Status drops the movie, the Favourite unmarks it.
  const toggleStatus = (status: Status) => toggle.mutate({ status: movie.data?.status === status ? null : status })
  const toggleFavourite = () => toggle.mutate({ favourite: !movie.data?.favourite })

  return (
    <View style={styles.screen}>
      <View style={{ paddingTop: top + 8, paddingHorizontal: 8 }}>
        <Pressable style={styles.back} onPress={() => router.back()} accessibilityRole="button" accessibilityLabel="Back">
          <Svg
            width={22}
            height={22}
            viewBox="0 0 24 24"
            fill="none"
            stroke={colors.accent}
            strokeWidth={2}
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <Path d="M15 5l-7 7 7 7" />
          </Svg>
          <Text style={styles.backText}>Back</Text>
        </Pressable>
      </View>
      {movie.isPending ? (
        <ActivityIndicator style={styles.center} color={colors.muted} />
      ) : movie.isError ? (
        <View style={styles.center}>
          <Text style={styles.message}>Couldn't load this movie.</Text>
          <Pressable style={styles.retry} onPress={() => movie.refetch()} accessibilityRole="button">
            <Text style={styles.retryText}>Try again</Text>
          </Pressable>
        </View>
      ) : (
        <ScrollView contentContainerStyle={styles.body}>
          <View style={styles.hero}>
            <Poster movie={movie.data} style={styles.poster} />
            <View style={styles.heading}>
              <Text style={styles.title} accessibilityRole="header">
                {movie.data.title}
              </Text>
              {movie.data.year !== null && <Text style={styles.year}>{movie.data.year}</Text>}
              <Text style={[styles.status, movie.data.status && { color: colors.accent }]}>
                {movie.data.status === 'to_watch'
                  ? 'On To watch'
                  : movie.data.watchedAt
                    ? `Watched on ${new Date(movie.data.watchedAt).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })}`
                    : 'Not in your lists'}
              </Text>
            </View>
          </View>
          {!!movie.data.overview && <Text style={styles.overview}>{movie.data.overview}</Text>}
        </ScrollView>
      )}
      {movie.isSuccess && (
        <View style={styles.buttons} accessibilityLabel="Your collection">
          <ToggleButton
            label="To watch"
            on={movie.data.status === 'to_watch'}
            disabled={toggle.isPending}
            onPress={() => toggleStatus('to_watch')}
          >
            <Path d="M6 4h12v17l-6-4-6 4z" />
          </ToggleButton>
          <ToggleButton
            label="Watched"
            on={movie.data.status === 'watched'}
            disabled={toggle.isPending}
            onPress={() => toggleStatus('watched')}
          >
            <Circle cx={12} cy={12} r={9} />
            <Path d="M8 12.5l2.5 2.5L16 9.5" />
          </ToggleButton>
          <ToggleButton label="Favourite" on={movie.data.favourite} disabled={toggle.isPending} onPress={toggleFavourite}>
            <Path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z" />
          </ToggleButton>
        </View>
      )}
    </View>
  )
}

type ToggleButtonProps = { label: string; on: boolean; disabled: boolean; onPress: () => void; children: ReactNode }

function ToggleButton({ label, on, disabled, onPress, children }: ToggleButtonProps) {
  const fg = on ? colors.background : colors.text
  return (
    <Pressable
      style={({ pressed }) => [styles.button, on && styles.buttonOn, (pressed || disabled) && { opacity: 0.6 }]}
      onPress={onPress}
      disabled={disabled}
      accessibilityRole="togglebutton"
      accessibilityState={{ checked: on, disabled }}
    >
      <Svg
        width={20}
        height={20}
        viewBox="0 0 24 24"
        fill="none"
        stroke={fg}
        strokeWidth={1.8}
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        {children}
      </Svg>
      <Text style={[styles.buttonText, { color: fg }]}>{label}</Text>
    </Pressable>
  )
}

const styles = StyleSheet.create({
  screen: { flex: 1 },
  back: { flexDirection: 'row', alignItems: 'center', gap: 2, height: 44, paddingHorizontal: 12, alignSelf: 'flex-start' },
  backText: { fontFamily: fonts.medium, fontSize: 16, color: colors.accent },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 40, gap: 16 },
  message: { fontFamily: fonts.regular, fontSize: 16, color: colors.muted, textAlign: 'center' },
  retry: {
    height: 44,
    paddingHorizontal: 20,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.buttonBorder,
    justifyContent: 'center',
  },
  retryText: { fontFamily: fonts.semibold, fontSize: 15, color: colors.text },
  body: { paddingTop: 12, paddingHorizontal: 20, paddingBottom: 20, gap: 24 },
  hero: { flexDirection: 'row', alignItems: 'flex-end', gap: 18 },
  poster: { width: 140, height: 210, borderRadius: 8 },
  heading: { flex: 1, gap: 6, paddingBottom: 4 },
  title: { fontFamily: fonts.title, fontSize: 30, lineHeight: 33, color: colors.text },
  year: { fontFamily: fonts.regular, fontSize: 15, color: colors.muted },
  status: { fontFamily: fonts.semibold, fontSize: 13, color: colors.muted },
  buttons: { flexDirection: 'row', gap: 10, paddingHorizontal: 20, paddingTop: 12, paddingBottom: 20 },
  button: {
    flex: 1,
    height: 64,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.buttonBorder,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 4,
  },
  buttonOn: { backgroundColor: colors.accent, borderColor: colors.accent },
  buttonText: { fontFamily: fonts.semibold, fontSize: 13 },
  overview: { fontFamily: fonts.regular, fontSize: 15, lineHeight: 23, color: '#D6CFC2' },
})
