import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '@/lib/api'

const KEY = ['session']

// Đang đăng nhập với tài khoản nào; lỗi 401 nghĩa là chưa đăng nhập.
export function useSession() {
  return useQuery({
    queryKey: KEY,
    queryFn: () => api<{ username: string }>('/session'),
    retry: false,
    staleTime: Infinity,
  })
}

export function useLogin() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (credentials: { username: string; password: string }) =>
      api<void>('/login', { method: 'POST', body: credentials }),
    onSuccess: () => client.invalidateQueries({ queryKey: KEY }),
  })
}

export function useLogout() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: () => api<void>('/logout', { method: 'POST' }),
    // Xoá mọi dữ liệu đã tải để người dùng sau trên cùng máy không thấy gì.
    onSettled: () => client.clear(),
  })
}
