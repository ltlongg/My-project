import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ThemeProvider } from 'next-themes'
import { createBrowserRouter, Navigate, RouterProvider } from 'react-router'

import { AppShell } from '@/components/app-shell'
import { Toaster } from '@/components/ui/sonner'
import { ApiError, setUnauthorizedHandler } from '@/lib/api'
import { EditChannelPage, NewChannelPage } from '@/pages/channel-form'
import { ChannelsPage } from '@/pages/channels'
import { LoginPage } from '@/pages/login'
import { NotFoundPage } from '@/pages/not-found'
import { EditSectionPage, NewSectionPage } from '@/pages/section-form'
import { SectionsPage } from '@/pages/sections'
import { EditSourcePage, NewSourcePage } from '@/pages/source-form'
import { SourcesPage } from '@/pages/sources'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Lỗi 4xx (chưa đăng nhập, không tìm thấy) không tự hết khi thử lại.
      retry: (count, error) => !(error instanceof ApiError && error.status < 500) && count < 2,
    },
  },
})

// Mọi trang trừ đăng nhập nằm trong AppShell, nơi chặn người chưa đăng nhập.
const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  {
    element: <AppShell />,
    children: [
      { index: true, element: <Navigate to="/sections" replace /> },
      { path: 'sections', element: <SectionsPage /> },
      { path: 'sections/new', element: <NewSectionPage /> },
      { path: 'sections/:id', element: <EditSectionPage /> },
      { path: 'sources', element: <SourcesPage /> },
      { path: 'sources/new', element: <NewSourcePage /> },
      { path: 'sources/:id', element: <EditSourcePage /> },
      { path: 'channels', element: <ChannelsPage /> },
      { path: 'channels/new', element: <NewChannelPage /> },
      { path: 'channels/:id', element: <EditChannelPage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
])

// Phiên hết hạn giữa chừng: bỏ dữ liệu đã tải và về trang đăng nhập.
setUnauthorizedHandler(() => {
  if (router.state.location.pathname === '/login') return
  queryClient.clear()
  void router.navigate('/login', { state: { from: router.state.location.pathname } })
})

export function App() {
  return (
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
        <Toaster position="top-center" richColors />
      </QueryClientProvider>
    </ThemeProvider>
  )
}
