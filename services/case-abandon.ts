import { supabase } from '@/lib/supabase'

export async function abandonCase(sessionId: string): Promise<void> {
  const { error } = await supabase.functions.invoke('case-abandon', {
    body: { sessionId },
  })
  if (error) throw new Error(error.message)
}
