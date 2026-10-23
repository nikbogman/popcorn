import { CollectionList } from '@/components/collection-list'

export default function Favourites() {
  return <CollectionList title="Favourites" filter={{ favourite: true }} empty="No favourites yet." />
}
