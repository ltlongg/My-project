import { Link } from 'react-router'

import { Button } from '@/components/ui/button'

export function NotFoundPage() {
  return (
    <div className="flex flex-col items-center py-16 text-center">
      <p className="text-lg font-medium">Không có trang này</p>
      <p className="mt-1 mb-4 text-sm text-muted-foreground">Đường dẫn sai hoặc trang đã bị bỏ.</p>
      <Button asChild variant="outline">
        <Link to="/sections">Về trang Chuyên mục</Link>
      </Button>
    </div>
  )
}
