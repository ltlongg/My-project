import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '@/lib/api'
import type { Kind } from '@/lib/kinds'

export type Source = {
  id: number
  kind: string
  name: string
  url: string
  is_enabled: boolean
  section_ids: number[]
  // Lần thu thập gần nhất, lấy được hay không; chưa lần nào thì null.
  last_fetched_at: string | null
  // Lỗi của lần thu thập gần nhất; lấy được thì null.
  last_error: string | null
  // Số Bài gốc xuất hiện trong 7 ngày qua.
  recent_articles: number
}

export type SourceFields = Pick<Source, 'name' | 'url' | 'section_ids'>

export type SampleArticle = {
  title: string
  url: string
  published_at: string | null
  description: string | null
}

export type SourceTrial = {
  articles: SampleArticle[]
  // Số Bài gốc Nguồn đang trả về, kể cả những bài không hiện.
  total: number
  error: string | null
}

const KEY = ['sources']

export function useSources() {
  return useQuery({ queryKey: KEY, queryFn: () => api<Source[]>('/sources') })
}

export function useSource(id: number) {
  return useQuery({ queryKey: [...KEY, id], queryFn: () => api<Source>(`/sources/${id}`) })
}

export function useSourceKinds() {
  return useQuery({
    queryKey: ['source-kinds'],
    queryFn: () => api<Kind[]>('/sources/kinds'),
    staleTime: Infinity,
  })
}

export function useCreateSource() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (fields: SourceFields & { kind: string }) =>
      api<Source>('/sources', { method: 'POST', body: fields }),
    onSuccess: () => client.invalidateQueries({ queryKey: KEY }),
  })
}

export function useUpdateSource(id: number) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (changes: Partial<SourceFields & { is_enabled: boolean }>) =>
      api<Source>(`/sources/${id}`, { method: 'PATCH', body: changes }),
    onSuccess: (source) => {
      client.setQueryData([...KEY, id], source)
      return client.invalidateQueries({ queryKey: KEY })
    },
  })
}

// Lấy thử một Nguồn chưa lưu; máy chủ không lưu gì.
export function useTrySource() {
  return useMutation({
    mutationFn: (trial: { kind: string; url: string }) =>
      api<SourceTrial>('/sources/test', { method: 'POST', body: trial }),
  })
}
