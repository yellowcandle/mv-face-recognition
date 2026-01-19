import { useState } from "react";
import { AppShell } from "./components";

export function ShellPreview() {
  const [currentPath, setCurrentPath] = useState("/player");
  const [locale, setLocale] = useState<"en" | "zh">("zh");
  const [theme, setTheme] = useState<"dark" | "light">("dark");

  const sectionContent: Record<string, { title: string; titleZh: string; description: string; descriptionZh: string }> = {
    "/player": {
      title: "Video Player",
      titleZh: "影片播放",
      description: "Watch videos with real-time face overlays and contestant thumbnails.",
      descriptionZh: "觀看帶有即時人臉標記和參賽者縮圖的影片。",
    },
    "/contestants": {
      title: "Contestants",
      titleZh: "參賽者",
      description: "Browse all contestants and view their appearance history.",
      descriptionZh: "瀏覽所有參賽者並查看其出場記錄。",
    },
    "/analytics": {
      title: "Analytics",
      titleZh: "數據分析",
      description: "View screen time statistics and co-appearance patterns.",
      descriptionZh: "查看螢幕時間統計和共同出場模式。",
    },
    "/ingestion": {
      title: "Video Ingestion",
      titleZh: "影片上載",
      description: "Submit YouTube URLs and monitor processing status.",
      descriptionZh: "提交 YouTube 連結並監控處理狀態。",
    },
    "/flagging": {
      title: "Face Flagging",
      titleZh: "標記修正",
      description: "Review and correct face identifications.",
      descriptionZh: "審核並修正人臉識別結果。",
    },
  };

  const content = sectionContent[currentPath] || sectionContent["/player"];
  const title = locale === "zh" ? content.titleZh : content.title;
  const description = locale === "zh" ? content.descriptionZh : content.description;

  return (
    <AppShell
      currentPath={currentPath}
      userName="用戶名稱"
      locale={locale}
      theme={theme}
      onNavigate={setCurrentPath}
      onThemeChange={setTheme}
      onLocaleChange={setLocale}
      onSignOut={() => console.log("Sign out clicked")}
    >
      <div className="max-w-4xl">
        {/* Page Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-semibold text-white mb-2">{title}</h1>
          <p className="text-slate-400">{description}</p>
        </div>

        {/* Placeholder Content */}
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div
              key={i}
              className="bg-slate-800/50 border border-slate-700 rounded-xl p-6 h-40 flex items-center justify-center"
            >
              <span className="text-slate-500 text-sm">
                {locale === "zh" ? `內容區塊 ${i}` : `Content Block ${i}`}
              </span>
            </div>
          ))}
        </div>

        {/* Section Info */}
        <div className="mt-8 p-4 bg-slate-800/30 border border-slate-700 rounded-lg">
          <p className="text-sm text-slate-400">
            {locale === "zh"
              ? "這是應用程式外殼的預覽。點擊側邊欄導航項目以切換不同頁面。"
              : "This is a preview of the application shell. Click sidebar navigation items to switch between sections."}
          </p>
        </div>
      </div>
    </AppShell>
  );
}

export default ShellPreview;
