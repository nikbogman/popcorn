import { Link } from 'expo-router'
import { StyleSheet, Text, View } from 'react-native'

import { colors, fonts } from '@/theme'

export function EmptyList({ text }: { text: string }) {
  return (
    <View style={styles.box}>
      <Text style={styles.text}>
        {text} Find a movie in{' '}
        <Link href="/" style={styles.link}>
          Search
        </Link>
        .
      </Text>
    </View>
  )
}

const styles = StyleSheet.create({
  box: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 40 },
  text: { fontFamily: fonts.regular, fontSize: 16, lineHeight: 24, color: colors.muted, textAlign: 'center' },
  link: { fontFamily: fonts.semibold, color: colors.accent },
})
