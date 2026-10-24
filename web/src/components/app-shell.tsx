import { LogOutIcon, MenuIcon, NewspaperIcon, UserIcon } from 'lucide-react'
import { useState } from 'react'
import { Navigate, NavLink, Outlet, useLocation, useNavigate } from 'react-router'

import { NAV } from '@/components/nav'
import { ThemeMenu } from '@/components/theme-menu'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Sheet, SheetContent, SheetDescription, SheetTitle, SheetTrigger } from '@/components/ui/sheet'
import { Skeleton } from '@/components/ui/skeleton'
import { useLogout, useSession } from '@/lib/session'
import { cn } from '@/lib/utils'

// Khung của mọi trang sau đăng nhập: thanh điều hướng ba tầng bên trái (trên điện thoại là ngăn
// kéo từ nút menu), thanh trên cùng có chế độ sáng tối và tài khoản.
export function AppShell() {
  const session = useSession()
  const location = useLocation()

  if (session.isPending) {
    return (
      <div className="flex min-h-svh items-center justify-center">
        <Skeleton className="h-6 w-40" />
      </div>
    )
  }
  if (session.isError) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }

  return (
    <div className="flex min-h-svh">
      <aside className="sticky top-0 hidden h-svh w-64 shrink-0 flex-col border-r bg-sidebar md:flex">
        <Brand />
        <Nav />
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar username={session.data.username} />
        <main className="mx-auto w-full max-w-4xl flex-1 px-4 py-6 sm:px-6 md:py-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

function Brand() {
  return (
    <div className="flex h-14 items-center gap-2 px-4">
      <span className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
        <NewspaperIcon className="size-4" />
      </span>
      <div className="leading-tight">
        <div className="font-semibold">Siftly</div>
        <div className="text-xs text-muted-foreground">Bản tin tự động</div>
      </div>
    </div>
  )
}

function Nav({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav className="flex flex-col gap-5 overflow-y-auto px-3 py-4" aria-label="Điều hướng chính">
      {NAV.map(({ tier, items }) => (
        <div key={tier} className="flex flex-col gap-0.5">
          <div className="px-2 pb-1 text-xs font-medium text-muted-foreground">{tier}</div>
          {items.map(({ label, icon: Icon, to }) =>
            to ? (
              <NavLink
                key={label}
                to={to}
                onClick={onNavigate}
                className={({ isActive }) =>
                  cn(
                    'flex h-9 items-center gap-2.5 rounded-lg px-2 text-sm transition-colors',
                    isActive
                      ? 'bg-sidebar-accent font-medium text-sidebar-accent-foreground'
                      : 'text-sidebar-foreground hover:bg-muted',
                  )
                }
              >
                <Icon className="size-4" />
                {label}
              </NavLink>
            ) : (
              <span
                key={label}
                aria-disabled="true"
                className="flex h-9 items-center gap-2.5 rounded-lg px-2 text-sm text-muted-foreground/70"
              >
                <Icon className="size-4" />
                {label}
                <Badge variant="outline" className="ml-auto text-muted-foreground">
                  Sắp có
                </Badge>
              </span>
            ),
          )}
        </div>
      ))}
    </nav>
  )
}

function TopBar({ username }: { username: string }) {
  const [menuOpen, setMenuOpen] = useState(false)
  const logout = useLogout()
  const navigate = useNavigate()

  return (
    <header className="sticky top-0 z-10 flex h-14 items-center gap-2 border-b bg-background/90 px-2 backdrop-blur sm:px-4">
      <Sheet open={menuOpen} onOpenChange={setMenuOpen}>
        <SheetTrigger asChild>
          <Button variant="ghost" size="icon-lg" className="md:hidden" aria-label="Mở menu">
            <MenuIcon />
          </Button>
        </SheetTrigger>
        <SheetContent side="left" className="w-72 bg-sidebar p-0">
          <SheetTitle className="sr-only">Điều hướng</SheetTitle>
          <SheetDescription className="sr-only">Các trang của trang quản lí</SheetDescription>
          <Brand />
          <Nav onNavigate={() => setMenuOpen(false)} />
        </SheetContent>
      </Sheet>
      <div className="font-semibold md:hidden">Siftly</div>
      <div className="ml-auto flex items-center gap-1">
        <ThemeMenu />
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" aria-label="Tài khoản">
              <UserIcon />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuLabel className="font-normal text-muted-foreground">
              Đăng nhập là <span className="font-medium text-foreground">{username}</span>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              onSelect={() => logout.mutate(undefined, { onSettled: () => navigate('/login') })}
            >
              <LogOutIcon />
              Đăng xuất
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  )
}
