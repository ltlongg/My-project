import { Badge } from '@/components/ui/badge'

export function SectionStatus({ paused }: { paused: boolean }) {
  return paused ? (
    <Badge variant="warning">Tạm dừng</Badge>
  ) : (
    <Badge variant="success">Đang chạy</Badge>
  )
}
