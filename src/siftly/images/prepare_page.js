// Dọn một trang bài báo trước khi chụp, chạy trong trình duyệt qua page.evaluate.
//
// Bước "clean": gỡ bảng cookie, phát hiện tường phí, gỡ lớp phủ khác đang che giữa màn hình, rồi
// cuộn tới tiêu đề bài. Bước "settle", chạy sau khi trang đã đứng yên: cuộn lại vì bố cục có thể
// đã dịch (ảnh tải lười, quảng cáo nở ra), rồi ẩn mọi thứ dính trên màn hình như header hay thanh
// quảng cáo.
//
// Trả về {error: "bot" | "wall" | "no_headline"} khi trang không chụp được, ngược lại là {}.
(step) => {
  const CONSENT = /cookie|consent|gdpr|privacy|quyền riêng tư/i;
  const WALL = /subscribe|subscription|sign in|log in|đăng nhập|đăng ký|paywall|premium|continue reading|unlock/i;
  const BOT = /just a moment|attention required|access denied|are you a robot|human verification|verify you are human|confirm you are human|security check|captcha/i;
  // Khoảng chừa phía trên tiêu đề, theo đơn vị CSS.
  const MARGIN = 24;
  // Lớp phủ che từ chừng này phần màn hình trở lên là chặn người đọc, không phải thanh nhỏ.
  const BLOCKING_AREA = 0.3;

  const visible = (el) => {
    const style = getComputedStyle(el);
    const box = el.getBoundingClientRect();
    return (
      style.display !== "none" &&
      style.visibility !== "hidden" &&
      Number(style.opacity) > 0.05 &&
      box.width > 0 &&
      box.height > 0
    );
  };
  const describe = (el) =>
    `${el.id} ${el.className} ${el.getAttribute("aria-label") || ""} ${el.innerText || ""}`.slice(0, 3000);
  const floating = () =>
    [...document.querySelectorAll("body *")].filter((el) => {
      const position = getComputedStyle(el).position;
      return (position === "fixed" || position === "sticky") && visible(el);
    });
  const scrollTo = (headline) =>
    window.scrollTo({ top: headline.getBoundingClientRect().top + window.scrollY - MARGIN, behavior: "instant" });

  const headlines = [...document.querySelectorAll("h1")].filter(
    (h) => visible(h) && h.innerText.trim().length >= 8
  );
  const headline = headlines.find((h) => h.closest("article, main, [role=main]")) || headlines[0];
  if (BOT.test(document.title) || (headline && BOT.test(headline.innerText))) return { error: "bot" };
  if (!headline) return { error: "no_headline" };

  if (step === "clean") {
    for (const el of floating()) {
      if (!el.contains(headline) && CONSENT.test(describe(el))) el.remove();
    }
    const center = document.elementFromPoint(innerWidth / 2, innerHeight / 2);
    for (let el = center; el && el !== document.body; el = el.parentElement) {
      if (getComputedStyle(el).position !== "fixed") continue;
      const box = el.getBoundingClientRect();
      if (box.width * box.height < BLOCKING_AREA * innerWidth * innerHeight) continue;
      if (WALL.test(describe(el))) return { error: "wall" };
      el.remove();
      break;
    }
    // Hộp hỏi cookie và lớp phủ thường khoá cuộn trang.
    for (const el of [document.documentElement, document.body]) {
      el.style.setProperty("overflow", "visible", "important");
    }
    scrollTo(headline);
    return {};
  }

  scrollTo(headline);
  for (const el of floating()) {
    // Làm trong suốt thay vì ẩn: phần tử con có thể tự đặt visibility, và gỡ khỏi bố cục thì
    // phần tử dính kéo cả trang dịch đi.
    if (!el.contains(headline)) el.style.setProperty("opacity", "0", "important");
  }
  return {};
}
