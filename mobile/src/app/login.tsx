import { Image } from 'expo-image'
import { useState } from 'react'
import { KeyboardAvoidingView, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native'

import { logIn } from '@/api'
import { colors, fonts } from '@/theme'

export default function Login() {
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string>()
  const [pending, setPending] = useState(false)

  async function submit() {
    setPending(true)
    setError(undefined)
    // On success the token is stored and the root layout's guard swaps in the tabs.
    const failure = await logIn(password)
    setPending(false)
    setError(failure)
  }

  return (
    // Edge-to-edge Android no longer resizes the window for the keyboard, so pad on both platforms.
    <KeyboardAvoidingView style={styles.fill} behavior="padding">
      <Image source={require('../../assets/images/logo-halftone.png')} style={styles.logo} />
      <ScrollView contentContainerStyle={styles.screen} keyboardShouldPersistTaps="handled">
        <Image
          source={require('../../assets/images/wordmark.png')}
          style={styles.wordmark}
          accessibilityRole="header"
          accessibilityLabel="popcorn"
        />
        <View style={styles.form}>
          <View style={styles.field}>
            <Text style={styles.label}>Password</Text>
            <TextInput
              style={styles.input}
              value={password}
              onChangeText={setPassword}
              secureTextEntry
              autoComplete="current-password"
              textContentType="password"
              returnKeyType="go"
              onSubmitEditing={submit}
              accessibilityLabel="Password"
            />
          </View>
          {error && <Text style={styles.error}>{error}</Text>}
          <Pressable
            style={[styles.button, pending && { opacity: 0.6 }]}
            onPress={submit}
            disabled={pending || !password}
            accessibilityRole="button"
          >
            <Text style={styles.buttonText}>Log in</Text>
          </Pressable>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  )
}

const styles = StyleSheet.create({
  fill: { flex: 1, backgroundColor: colors.background },
  logo: { position: 'absolute', top: -135, right: -160, width: 560, height: 560 },
  screen: { flexGrow: 1, justifyContent: 'flex-end', gap: 40, paddingHorizontal: 28, paddingTop: 24, paddingBottom: 56 },
  wordmark: { width: 250, aspectRatio: 2721 / 536 },
  form: { gap: 20 },
  field: { gap: 8 },
  label: { fontFamily: fonts.medium, fontSize: 13, color: colors.muted },
  input: {
    height: 52,
    paddingHorizontal: 16,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    color: colors.text,
    fontFamily: fonts.regular,
    fontSize: 16,
  },
  error: { fontFamily: fonts.medium, fontSize: 14, color: colors.accent },
  button: { height: 52, marginTop: 8, borderRadius: 12, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.accent },
  buttonText: { fontFamily: fonts.semibold, fontSize: 16, color: colors.background },
})
