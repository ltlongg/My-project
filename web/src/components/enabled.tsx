import { toast } from 'sonner'

import { Badge } from '@/components/ui/badge'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'

// Trạng thái bật/tắt của một Nguồn hay Kênh đăng.
export function EnabledStatus({ enabled }: { enabled: boolean }) {
  return enabled ? <Badge variant="success">Đang bật</Badge> : <Badge variant="warning">Đã tắt</Badge>
}

// Công tắc bật/tắt áp dụng ngay khi bấm; `name` dùng trong thông báo kết quả.
export function EnabledSwitch({
  id,
  name,
  enabled,
  pending,
  onChange,
}: {
  id: string
  name: string
  enabled: boolean
  pending: boolean
  onChange: (enabled: boolean, done: { onSuccess: () => void; onError: (error: Error) => void }) => void
}) {
  return (
    <div className="flex items-center gap-2">
      <Switch
        id={id}
        checked={enabled}
        disabled={pending}
        onCheckedChange={(checked) =>
          onChange(checked, {
            onSuccess: () => toast.success(checked ? `Đã bật ${name}` : `Đã tắt ${name}`),
            onError: (error) => toast.error(error.message),
          })
        }
      />
      <Label htmlFor={id} className="font-normal">
        {enabled ? 'Đang bật' : 'Đã tắt'}
      </Label>
    </div>
  )
}
