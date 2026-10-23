import { StyleSheet, TextInput, View } from 'react-native'
import Svg, { Circle, Path } from 'react-native-svg'

import { colors, fonts } from '@/theme'

export function SearchField({
  value,
  onChangeText,
  placeholder,
  label,
}: {
  value: string
  onChangeText: (text: string) => void
  placeholder: string
  label: string
}) {
  return (
    <View style={styles.field}>
      <Svg
        style={styles.icon}
        width={20}
        height={20}
        viewBox="0 0 24 24"
        fill="none"
        stroke={colors.muted}
        strokeWidth={1.8}
        strokeLinecap="round"
      >
        <Circle cx={11} cy={11} r={7} />
        <Path d="M20 20l-4-4" />
      </Svg>
      <TextInput
        style={styles.input}
        value={value}
        onChangeText={onChangeText}
        placeholder={placeholder}
        placeholderTextColor={colors.muted}
        returnKeyType="search"
        autoCorrect={false}
        accessibilityLabel={label}
      />
    </View>
  )
}

const styles = StyleSheet.create({
  field: { marginHorizontal: 20, marginBottom: 16, justifyContent: 'center' },
  icon: { position: 'absolute', left: 14, zIndex: 1 },
  input: {
    height: 48,
    paddingLeft: 44,
    paddingRight: 16,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    color: colors.text,
    fontFamily: fonts.regular,
    fontSize: 16,
  },
})
