import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import type { Kind } from '@/lib/kinds'

// Chọn loại Nguồn hay Kênh đăng trong số loại máy chủ có. Loại không đổi được sau khi tạo, nên ở
// trang sửa nó bị tắt.
export function KindSelect({
  id,
  kinds,
  value,
  onChange,
  disabled,
}: {
  id: string
  kinds: Kind[]
  value: string
  onChange: (kind: string) => void
  disabled?: boolean
}) {
  return (
    <Select value={value} onValueChange={onChange} disabled={disabled}>
      <SelectTrigger id={id} className="w-full sm:w-64">
        <SelectValue placeholder="Chọn loại" />
      </SelectTrigger>
      <SelectContent>
        {kinds.map((kind) => (
          <SelectItem key={kind.kind} value={kind.kind}>
            {kind.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
