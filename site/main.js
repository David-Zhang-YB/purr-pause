/* Purr Pause 落地页脚本
 *
 * 两件事，都是渐进增强——JS 挂了页面照常可用：
 *   1. 当 OSS 上确实有 latest.json（即国内源已就绪）时，把所有 [data-download]
 *      按钮切到国内 OSS 最新版（更快）并填充 [data-version] 文案；否则保留 HTML 里
 *      写死的 GitHub Releases 链接与 "v0.1.2" 文案，下载始终有效、绝不指向 404。
 *   2. 滚动揭示动画（IntersectionObserver）。
 *
 * OSS_BASE = 你的 OSS 桶的公网访问前缀，形如
 *   https://<桶名>.oss-cn-<region>.aliyuncs.com
 */

const OSS_BASE = "https://purr-pause.oss-cn-shenzhen.aliyuncs.com";

const LATEST_EXE  = OSS_BASE + "/PurrPause-latest-windows.exe";
const LATEST_JSON = OSS_BASE + "/latest.json";
const OSS_CONFIGURED = !OSS_BASE.includes("REPLACE_ME");

(function downloadLinks() {
  if (!OSS_CONFIGURED) return;  // 没配 OSS：保持 HTML 里的 GitHub 兜底

  const btns = document.querySelectorAll("[data-download]");
  const versionEls = document.querySelectorAll("[data-version]");

  // 下载按钮直接指向 OSS 国内源——页面跳转下载不受 CORS 限制，且该文件已托管在 OSS 上。
  btns.forEach(function (b) { b.href = LATEST_EXE; });

  // 版本号/体积：尝试读 latest.json 填充。跨域 fetch 需 OSS 配好 CORS（指向站点域名）；
  // 读不到就保留 HTML 里的静态兜底文案，不影响下载。
  fetch(LATEST_JSON, { cache: "no-store" })
    .then(function (res) {
      if (!res.ok) throw new Error("HTTP " + res.status);
      return res.json();
    })
    .then(function (data) {
      if (!data || !data.version) return;
      if (data.url) btns.forEach(function (b) { b.href = data.url; });
      let text = "最新版本 v" + data.version;
      if (typeof data.size === "number" && data.size > 0) {
        text += " · " + (data.size / 1024 / 1024).toFixed(0) + " MB";
      }
      versionEls.forEach(function (el) { el.textContent = text; });
    })
    .catch(function () { /* CORS 未配 / OSS 不可达 → 保留静态版本号，下载仍走 OSS */ });
})();

(function scrollReveal() {
  const items = document.querySelectorAll(".reveal");
  if (!items.length) return;

  // 不支持 IntersectionObserver（或用户偏好减少动效）→ 直接全部显示
  const reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (!("IntersectionObserver" in window) || reduce) {
    items.forEach(function (el) { el.classList.add("in"); });
    return;
  }

  const io = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      if (e.isIntersecting) {
        e.target.classList.add("in");
        io.unobserve(e.target);
      }
    });
  }, { threshold: 0.12, rootMargin: "0px 0px -8% 0px" });

  items.forEach(function (el) { io.observe(el); });
})();
