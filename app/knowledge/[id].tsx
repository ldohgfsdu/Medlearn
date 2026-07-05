import { Redirect } from 'expo-router'

/**
 * Legacy route ? current rebuild routes legacy knowledge detail traffic back
 * to the textbook map until the new textbook detail contract is restored.
 */
export default function KnowledgeLegacyRedirect() {
  return <Redirect href="/map" />
}
