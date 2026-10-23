import { useState } from 'react'
import { FlatList, StyleSheet, Text, View } from 'react-native'

import { useSearch } from '@/movies'
import { MovieRow } from '@/components/movie-row'
import { SearchField } from '@/components/search-field'
import { ScreenHeader } from '@/components/screen-header'
import { colors, fonts } from '@/theme'
import { useDebounced } from '@/use-debounced'

export default function Search() {
  const [text, setText] = useState('')
  const q = useDebounced(text.trim(), 300)
  const search = useSearch(q)

  return (
    <View style={styles.screen}>
      <ScreenHeader title="Search" />
      <SearchField value={text} onChangeText={setText} placeholder="Movie title" label="Search movies by title" />
      {search.isError ? (
        <Text style={styles.message}>Couldn't search right now. Try again in a moment.</Text>
      ) : (
        <FlatList
          data={q ? search.data : []}
          keyExtractor={(m) => String(m.tmdbId)}
          renderItem={({ item }) => <MovieRow movie={item} />}
          keyboardShouldPersistTaps="handled"
          keyboardDismissMode="on-drag"
          ListEmptyComponent={q && search.isSuccess ? <Text style={styles.message}>No movies match “{q}”.</Text> : null}
        />
      )}
    </View>
  )
}

const styles = StyleSheet.create({
  screen: { flex: 1 },
  message: { padding: 20, fontFamily: fonts.regular, fontSize: 16, color: colors.muted, textAlign: 'center' },
})
