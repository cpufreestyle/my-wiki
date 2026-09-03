/**
 * theme.js — MyWiki 网页版共享主题逻辑（深色/浅色）
 *
 * 所有 *_web.html 共用：读取/持久化 localStorage("mywiki-theme")，
 * 若页面存在 #themeToggle 按钮则自动绑定切换与图标（🌙/☀️）。
 * 页面在自身脚本执行前先引入本文件，保证首屏无闪白。
 */
(function () {
    function getTheme() {
        try { return localStorage.getItem("mywiki-theme") || "light"; }
        catch { return "light"; }
    }
    function applyTheme(t) {
        document.documentElement.setAttribute("data-theme", t);
        const toggle = document.getElementById("themeToggle");
        if (toggle) toggle.textContent = t === "dark" ? "☀️" : "🌙";
        try { localStorage.setItem("mywiki-theme", t); } catch {}
    }
    applyTheme(getTheme());
    // 脚本可能在按钮 DOM 之前加载，绑定延迟到 DOM 就绪
    document.addEventListener("DOMContentLoaded", () => {
        const toggle = document.getElementById("themeToggle");
        if (toggle) {
            toggle.addEventListener("click", () => {
                const cur = document.documentElement.getAttribute("data-theme");
                applyTheme(cur === "dark" ? "light" : "dark");
            });
        }
    });
})();
