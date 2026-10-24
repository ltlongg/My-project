import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '@/lib/api'
import type { Kind } from '@/lib/kinds'

export type Channel = {
  id: number
  kind: string
  name: string
  address: string
  is_enabled: boolean
  section_ids: number[]
}

export type ChannelFields = Pick<Channel, 'name' | 'address' | 'section_ids'>

const KEY = ['channels']

export function useChannels() {
  return useQuery({ queryKey: KEY, queryFn: () => api<Channel[]>('/channels') })
}

export function useChannel(id: number) {
  return useQuery({ queryKey: [...KEY, id], queryFn: () => api<Channel>(`/channels/${id}`) })
}

export function useChannelKinds() {
  return useQuery({
    queryKey: ['channel-kinds'],
    queryFn: () => api<Kind[]>('/channels/kinds'),
    staleTime: Infinity,
  })
}

export function useCreateChannel() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (fields: ChannelFields & { kind: string }) =>
      api<Channel>('/channels', { method: 'POST', body: fields }),
    onSuccess: () => client.invalidateQueries({ queryKey: KEY }),
  })
}

export function useUpdateChannel(id: number) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (changes: Partial<ChannelFields & { is_enabled: boolean }>) =>
      api<Channel>(`/channels/${id}`, { method: 'PATCH', body: changes }),
    onSuccess: (channel) => {
      client.setQueryData([...KEY, id], channel)
      return client.invalidateQueries({ queryKey: KEY })
    },
  })
}

// Gửi tin nhắn thử tới một Kênh đăng, đã lưu hay chưa; `error` là null khi gửi được.
export function useTryChannel() {
  return useMutation({
    mutationFn: (trial: { kind: string; address: string }) =>
      api<{ error: string | null }>('/channels/test', { method: 'POST', body: trial }),
  })
}
