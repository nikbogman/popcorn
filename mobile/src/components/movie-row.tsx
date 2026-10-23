import { Image } from 'expo-image'
import { router } from 'expo-router'
import { Pressable, StyleSheet, Text, View } from 'react-native'

import type { MovieSummary } from '@/movies'
import { colors, fonts } from '@/theme'

// Muted tones for the placeholder block shown when TMDB has no poster.
const TONES = ['#4A3B2A', '#2F3A33', '#3B2F3A', '#2E3440', '#40352A', '#33302A']

type PosterStyle = { width: number; height: number; borderRadius: number }

export function Poster({ movie, style }: { movie: MovieSummary; style: PosterStyle }) {
  return movie.posterUrl ? (
    <Image source={movie.posterUrl} style={style} transition={150} accessibilityIgnoresInvertColors />
  ) : (
    <View style={[style, { backgroundColor: TONES[movie.tmdbId % TONES.length] }]} />
  )
}

export function MovieRow({ movie }: { movie: MovieSummary }) {
  return (
    <Pressable
      style={({ pressed }) => [styles.row, pressed && styles.pressed]}
      onPress={() => router.push({ pathname: '/movie/[tmdbId]', params: { tmdbId: movie.tmdbId } })}
      accessibilityRole="button"
    >
      <Poster movie={movie} style={styles.poster} />
      <View style={styles.text}>
        <Text style={styles.title} numberOfLines={2}>
          {movie.title}
        </Text>
        {movie.year !== null && <Text style={styles.year}>{movie.year}</Text>}
      </View>
    </Pressable>
  )
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 14,
    minHeight: 72,
    paddingVertical: 10,
    paddingHorizontal: 20,
    borderBottomWidth: 1,
    borderBottomColor: '#2A2721',
  },
  pressed: { backgroundColor: colors.surface },
  poster: { width: 48, height: 72, borderRadius: 4 },
  text: { flex: 1, gap: 4 },
  title: { fontFamily: fonts.semibold, fontSize: 16, color: colors.text },
  year: { fontFamily: fonts.regular, fontSize: 13, color: colors.muted },
})
