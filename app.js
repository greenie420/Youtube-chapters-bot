// No backend, no build step: everything here just fetches the JSON files
// the crawler committed under /channels and renders them.
const Archive = (() => {
  const INDEX_URL = "channels/index.json";
  let cache = null;

  async function fetchIndex() {
    if (cache) return cache;
    const res = await fetch(INDEX_URL, { cache: "no-store" });
    if (!res.ok) throw new Error(`could not load ${INDEX_URL}`);
    cache = await res.json();
    return cache;
  }

  async function fetchVideo(channelId, videoId) {
    const res = await fetch(`channels/${channelId}/${videoId}.json`, { cache: "no-store" });
    if (!res.ok) throw new Error("video not found");
    return res.json();
  }

  function timeAgo(iso) {
    if (!iso) return "";
    const diff = (Date.now() - new Date(iso).getTime()) / 1000;
    const units = [
      ["year", 31536000], ["month", 2592000], ["day", 86400],
      ["hour", 3600], ["minute", 60],
    ];
    for (const [name, secs] of units) {
      const v = Math.floor(diff / secs);
      if (v >= 1) return `${v} ${name}${v > 1 ? "s" : ""} ago`;
    }
    return "just now";
  }

  function cardHTML(v) {
    const chapterCount = v.chapterTitles ? v.chapterTitles.length : 0;
    return `
      <a class="card" href="video.html?c=${encodeURIComponent(v.channelId)}&v=${encodeURIComponent(v.videoId)}">
        <img class="thumb" src="${v.thumbnail}" alt="" loading="lazy">
        <div class="body">
          <p class="title">${escapeHTML(v.title)}</p>
          <div class="meta">
            <span>${escapeHTML(v.channelName)}</span>
            <span class="chip">${chapterCount} ch</span>
          </div>
        </div>
      </a>`;
  }

  function escapeHTML(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
  }

  function renderStats(target, stats) {
    target.innerHTML = `
      <div class="stat"><span class="num">${stats.videos ?? 0}</span><span class="label">videos</span></div>
      <div class="stat"><span class="num">${stats.channels ?? 0}</span><span class="label">channels</span></div>
      <div class="stat"><span class="num">${stats.comments ?? 0}</span><span class="label">comments posted</span></div>
      <div class="stat"><span class="num">${stats.avgChapters ?? 0}</span><span class="label">avg chapters / video</span></div>`;
  }

  // Header behaviour shared by every page: theme toggle + global search.
  function initHeader() {
    const toggle = document.getElementById("theme-toggle");
    if (toggle) {
      toggle.addEventListener("click", () => {
        const html = document.documentElement;
        const current = html.getAttribute("data-theme") ||
          (matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark");
        html.setAttribute("data-theme", current === "dark" ? "light" : "dark");
      });
    }

    const search = document.getElementById("search");
    if (search) {
      search.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && search.value.trim()) {
          location.href = `index.html?q=${encodeURIComponent(search.value.trim())}`;
        }
      });
    }
  }

  function matchesQuery(v, q) {
    q = q.toLowerCase();
    return (
      v.title.toLowerCase().includes(q) ||
      v.channelName.toLowerCase().includes(q) ||
      (v.chapterTitles || []).some((t) => t.toLowerCase().includes(q))
    );
  }

  return { fetchIndex, fetchVideo, timeAgo, cardHTML, renderStats, initHeader, matchesQuery, escapeHTML };
})();
