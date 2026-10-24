import {
  BookTextIcon,
  CalendarClockIcon,
  LightbulbIcon,
  NewspaperIcon,
  RssIcon,
  SearchIcon,
  SendIcon,
  type LucideIcon,
} from 'lucide-react'

export type NavItem = {
  label: string
  icon: LucideIcon
  // Chưa có đường dẫn là trang của một ticket sau: hiện mờ, kèm nhãn "Sắp có".
  to?: string
}

// Ba tầng của trang quản lí. Ticket sau thêm `to` cho mục của mình, hoặc thêm mục mới.
export const NAV: { tier: string; items: NavItem[] }[] = [
  {
    tier: 'Thiết lập',
    items: [
      { label: 'Chuyên mục', icon: NewspaperIcon, to: '/sections' },
      { label: 'Nguồn', icon: RssIcon, to: '/sources' },
      { label: 'Kênh đăng', icon: SendIcon, to: '/channels' },
    ],
  },
  {
    tier: 'Theo dõi',
    items: [
      { label: 'Kỳ', icon: CalendarClockIcon },
      { label: 'Tìm Tin', icon: SearchIcon },
    ],
  },
  {
    tier: 'Cải tiến',
    items: [
      { label: 'Hướng dẫn', icon: BookTextIcon },
      { label: 'Đề xuất cải tiến', icon: LightbulbIcon },
    ],
  },
]
