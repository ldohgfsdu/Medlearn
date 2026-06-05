import { useQuery } from '@tanstack/react-query'
import { supabase } from '@/lib/supabase'

/**
 * 获取所有医学系统（对应教材的"篇"）
 */
export function useSubjects() {
  return useQuery({
    queryKey: ['subjects'],
    queryFn: async () => {
      const { data, error } = await supabase
        .from('knowledge_nodes')
        .select('subject')

      if (error) throw error
      const subjects = Array.from(new Set(data.map(i => i.subject))).filter(Boolean)
      return subjects
    }
  })
}

/**
 * 获取某个系统下的所有章节和知识点
 */
export function useTreeBySubject(subject: string) {
  return useQuery({
    queryKey: ['tree', subject],
    queryFn: async () => {
      const { data, error } = await supabase
        .from('knowledge_nodes')
        .select('*')
        .eq('subject', subject)
        .order('id', { ascending: true })

      if (error) throw error

      // 将平铺的数据组装成树状结构：Chapter -> Nodes
      const tree: Record<string, any[]> = {}
      data.forEach(node => {
        const chapter = node.chapter || '其他'
        if (!tree[chapter]) tree[chapter] = []
        tree[chapter].push(node)
      })
      return tree
    },
    enabled: !!subject
  })
}
