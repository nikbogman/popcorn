import { CollectionList } from '@/components/collection-list'

export default function ToWatch() {
  return <CollectionList title="To watch" filter={{ status: 'to_watch' }} empty="Nothing to watch yet." />
}
