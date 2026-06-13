import { Redirect, useLocalSearchParams } from 'expo-router'

/**
 * Legacy route — redirects to the canonical knowledge detail page.
 * Old UI preserved in app_ui_legacy_backup_20260613/
 */
export default function KnowledgeLegacyRedirect() {
  const { id, title } = useLocalSearchParams<{ id: string; title?: string }>()

  if (!id) {
    return <Redirect href="/(tabs)/learn" />
  }

  return (
    <Redirect
      href={{
        pathname: '/node/[id]',
        params: title ? { id, title } : { id },
      }}
    />
  )
}