import { CollectionList } from '@/components/collection-list'

export default function Watched() {
  return <CollectionList title="Watched" filter={{ status: 'watched' }} empty="Nothing watched yet." />
}
