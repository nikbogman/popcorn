import { router } from 'expo-router'
import { useState, type ReactNode } from 'react'
import { ActivityIndicator, Alert, FlatList, Linking, Pressable, StyleSheet, Text, TextInput, View } from 'react-native'
import Svg, { Circle, Path } from 'react-native-svg'

import { useMovie } from '@/collection'
import { Poster } from '@/components/movie-row'
import { ScreenHeader } from '@/components/screen-header'
import { inProgress, useRequests, useRetry, useShareReel, type ReelRequest } from '@/reels'
import { colors, fonts } from '@/theme'

const STEPS = ['In Instagram, tap Share on a reel', 'Pick popcorn from the share list', 'The title shows up here']

export default function Requests() {
  const requests = useRequests()
  return (
    <>
      <ScreenHeader title="Requests" logout />
      <Text style={styles.subtitle}>Reels you shared from Instagram.</Text>
      <PasteLink />
      {requests.isPending ? (
        <ActivityIndicator style={styles.center} color={colors.muted} />
      ) : requests.isError ? (
        <Text style={styles.message}>Couldn't load your requests. Try again in a moment.</Text>
      ) : (
        <FlatList
          data={requests.data}
          keyExtractor={(r) => r.id}
          renderItem={({ item }) => <RequestRow request={item} />}
          keyboardShouldPersistTaps="handled"
          contentContainerStyle={requests.data.length === 0 && styles.center}
          ListEmptyComponent={<Empty />}
        />
      )}
    </>
  )
}

/** For when sharing isn't available, e.g. in Expo Go: paste a reel link instead. */
function PasteLink() {
  const [url, setUrl] = useState('')
  const share = useShareReel()
  const send = () =>
    share.mutate(url.trim(), {
      onSuccess: () => setUrl(''),
      onError: () => Alert.alert("Couldn't send it", 'Paste a link to an Instagram reel or post.'),
    })
  return (
    <View style={styles.paste}>
      <TextInput
        style={styles.input}
        value={url}
        onChangeText={setUrl}
        placeholder="Paste a reel link"
        placeholderTextColor={colors.muted}
        autoCapitalize="none"
        autoCorrect={false}
        keyboardType="url"
        returnKeyType="send"
        onSubmitEditing={send}
        accessibilityLabel="Reel link"
      />
      <Pressable
        style={({ pressed }) => [styles.button, (pressed || share.isPending || !url.trim()) && { opacity: 0.6 }]}
        onPress={send}
        disabled={share.isPending || !url.trim()}
        accessibilityRole="button"
      >
        <Text style={styles.buttonText}>Send</Text>
      </Pressable>
    </View>
  )
}

function RequestRow({ request: r }: { request: ReelRequest }) {
  const retry = useRetry()
  const shared = `Shared ${ago(r.createdAt)}`

  if (inProgress(r))
    return (
      <Row
        thumb={
          <View style={[styles.thumb, styles.pending]}>
            <ActivityIndicator color={colors.accent} />
          </View>
        }
        title="Finding the title…"
        detail={shared}
      />
    )

  if (r.status === 'failed')
    return (
      <Row
        thumb={<Thumb tone="#2A1D19" color="#E8846B" d={['M12 4l9 16H3z', 'M12 10v4', 'M12 17h.01']} />}
        title="Couldn't read the reel"
        dim
        detail={`Something went wrong · ${ago(r.createdAt)}`}
        detailColor="#E8846B"
        action={
          <Pressable
            style={({ pressed }) => [styles.retry, (pressed || retry.isPending) && { opacity: 0.6 }]}
            onPress={() => retry.mutate(r.id, { onError: () => Alert.alert("Couldn't retry", 'Try again in a moment.') })}
            disabled={retry.isPending}
            accessibilityRole="button"
          >
            <Text style={styles.retryText}>Retry</Text>
          </Pressable>
        }
      />
    )

  if (!r.title)
    return (
      <Row
        thumb={
          <Thumb
            tone={colors.surface}
            color={colors.tabInactive}
            d={['M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .8-1 1.5v.5', 'M12 17h.01']}
            circle
          />
        }
        title="No title found"
        dim
        detail={shared}
        action={
          <Pressable style={styles.link} onPress={() => Linking.openURL(r.url)} accessibilityRole="link">
            <Text style={styles.linkText}>Open reel</Text>
          </Pressable>
        }
      />
    )

  const { name, year, kind, tmdbId } = r.title
  const detail = [kind === 'tv' && 'TV', year, shared].filter(Boolean).join(' · ')
  // ponytail: TV shows and movies TMDB doesn't know have no movie page, so they're shown but not tappable.
  if (tmdbId === null) return <Row thumb={<View style={[styles.thumb, { backgroundColor: '#26303A' }]} />} title={name} detail={detail} />
  return (
    <Pressable
      style={({ pressed }) => pressed && { backgroundColor: colors.surface }}
      onPress={() => router.push({ pathname: '/movie/[tmdbId]', params: { tmdbId } })}
      accessibilityRole="button"
    >
      <Row thumb={<FoundPoster tmdbId={tmdbId} />} title={name} detail={detail} action={<Chevron />} />
    </Pressable>
  )
}

type RowProps = { thumb: ReactNode; title: string; detail: string; detailColor?: string; dim?: boolean; action?: ReactNode }

function Row({ thumb, title, detail, detailColor, dim, action }: RowProps) {
  return (
    <View style={styles.row}>
      {thumb}
      <View style={styles.text}>
        <Text style={[styles.title, dim && { color: '#D6CFC2' }]} numberOfLines={2}>
          {title}
        </Text>
        <Text style={[styles.detail, detailColor && { color: detailColor }]}>{detail}</Text>
      </View>
      {action}
    </View>
  )
}

/** The poster comes from the movie, which is then cached for its page. */
function FoundPoster({ tmdbId }: { tmdbId: number }) {
  const movie = useMovie(String(tmdbId))
  return movie.data ? (
    <Poster movie={movie.data} style={styles.thumb} />
  ) : (
    <View style={[styles.thumb, { backgroundColor: colors.surface }]} />
  )
}

function Thumb({ tone, color, d, circle }: { tone: string; color: string; d: string[]; circle?: boolean }) {
  return (
    <View style={[styles.thumb, styles.centered, { backgroundColor: tone }]}>
      <Svg
        width={22}
        height={22}
        viewBox="0 0 24 24"
        fill="none"
        stroke={color}
        strokeWidth={1.8}
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        {circle && <Circle cx={12} cy={12} r={9} />}
        {d.map((p) => (
          <Path key={p} d={p} />
        ))}
      </Svg>
    </View>
  )
}

function Chevron() {
  return (
    <Svg
      width={20}
      height={20}
      viewBox="0 0 24 24"
      fill="none"
      stroke={colors.tabInactive}
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <Path d="M9 5l7 7-7 7" />
    </Svg>
  )
}

function Empty() {
  return (
    <View style={styles.empty}>
      <Text style={styles.emptyTitle}>No requests yet</Text>
      <Text style={styles.emptyText}>Spot a movie or show in a reel? Send it here and popcorn will name it.</Text>
      {STEPS.map((step, i) => (
        <View key={step} style={styles.step}>
          <View style={styles.stepNumber}>
            <Text style={styles.stepNumberText}>{i + 1}</Text>
          </View>
          <Text style={styles.stepText}>{step}</Text>
        </View>
      ))}
    </View>
  )
}

/** "just now", "12 min ago", "3 h ago", "yesterday", or the date. */
function ago(iso: string) {
  const min = Math.floor((Date.now() - new Date(iso).getTime()) / 60_000)
  if (min < 1) return 'just now'
  if (min < 60) return `${min} min ago`
  if (min < 24 * 60) return `${Math.floor(min / 60)} h ago`
  if (min < 48 * 60) return 'yesterday'
  return `on ${new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short' })}`
}

const styles = StyleSheet.create({
  subtitle: { marginTop: -8, marginBottom: 12, paddingHorizontal: 20, fontFamily: fonts.regular, fontSize: 14, color: colors.muted },
  center: { flexGrow: 1, justifyContent: 'center' },
  message: { padding: 20, fontFamily: fonts.regular, fontSize: 16, color: colors.muted, textAlign: 'center' },
  paste: { flexDirection: 'row', gap: 10, marginHorizontal: 20, marginBottom: 8 },
  input: {
    flex: 1,
    height: 48,
    paddingHorizontal: 16,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    color: colors.text,
    fontFamily: fonts.regular,
    fontSize: 16,
  },
  button: { height: 48, paddingHorizontal: 18, borderRadius: 12, backgroundColor: colors.accent, justifyContent: 'center' },
  buttonText: { fontFamily: fonts.semibold, fontSize: 15, color: colors.background },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 14,
    minHeight: 72,
    paddingVertical: 10,
    paddingLeft: 20,
    paddingRight: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#2A2721',
  },
  thumb: { width: 48, height: 72, borderRadius: 4 },
  centered: { alignItems: 'center', justifyContent: 'center' },
  pending: { alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderStyle: 'dashed', borderColor: colors.buttonBorder },
  text: { flex: 1, gap: 4 },
  title: { fontFamily: fonts.semibold, fontSize: 16, color: colors.text },
  detail: { fontFamily: fonts.regular, fontSize: 13, color: colors.muted },
  retry: {
    height: 44,
    paddingHorizontal: 14,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.buttonBorder,
    justifyContent: 'center',
  },
  retryText: { fontFamily: fonts.semibold, fontSize: 14, color: colors.text },
  link: { height: 44, paddingHorizontal: 8, justifyContent: 'center' },
  linkText: { fontFamily: fonts.semibold, fontSize: 14, color: colors.accent },
  empty: { paddingHorizontal: 36, gap: 14 },
  emptyTitle: { fontFamily: fonts.title, fontSize: 24, color: colors.text },
  emptyText: { fontFamily: fonts.regular, fontSize: 15, lineHeight: 23, color: colors.muted, marginBottom: 10 },
  step: { flexDirection: 'row', alignItems: 'center', gap: 14 },
  stepNumber: {
    width: 28,
    height: 28,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.buttonBorder,
    alignItems: 'center',
    justifyContent: 'center',
  },
  stepNumberText: { fontFamily: fonts.semibold, fontSize: 13, color: colors.accent },
  stepText: { flex: 1, fontFamily: fonts.regular, fontSize: 15, color: colors.text },
})
