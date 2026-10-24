import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '@/lib/api'

export type Section = {
  id: number
  // Mã dùng ở dòng lệnh; đặt một lần khi tạo, không đổi.
  slug: string
  name: string
  scope: string
  // Giờ Việt Nam, dạng "08:00".
  publish_time: string
  max_stories: number
  is_paused: boolean
}

export type SectionFields = Pick<Section, 'name' | 'scope' | 'publish_time' | 'max_stories'>

// Giới hạn trùng với API.
export const MIN_STORIES = 3
export const MAX_STORIES = 10

const KEY = ['sections']

export function useSections() {
  return useQuery({ queryKey: KEY, queryFn: () => api<Section[]>('/sections') })
}

export function useSection(id: number) {
  return useQuery({
    queryKey: [...KEY, id],
    queryFn: () => api<Section>(`/sections/${id}`),
  })
}

export function useCreateSection() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (fields: SectionFields) =>
      api<Section>('/sections', { method: 'POST', body: fields }),
    onSuccess: () => client.invalidateQueries({ queryKey: KEY }),
  })
}

export function useUpdateSection(id: number) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (changes: Partial<SectionFields & { is_paused: boolean }>) =>
      api<Section>(`/sections/${id}`, { method: 'PATCH', body: changes }),
    onSuccess: (section) => {
      client.setQueryData([...KEY, id], section)
      return client.invalidateQueries({ queryKey: KEY })
    },
  })
}

// Tên các Chuyên mục có mã số trong `ids`, ngăn bằng dấu phẩy; chưa tải xong thì undefined.
export function sectionNames(sections: Section[] | undefined, ids: number[]) {
  if (!sections) return undefined
  return sections
    .filter((section) => ids.includes(section.id))
    .map((section) => section.name)
    .join(', ')
}
