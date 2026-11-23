/**
 * Disha Pro Cloudflare Edge Worker
 * Handles 100% of Video Streaming & PDF Decryption at Cloudflare Edge
 * Zero Load on Render Backend | 100,000 Free Requests Daily
 */

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
  "Access-Control-Allow-Headers": "*",
  "Access-Control-Expose-Headers": "*",
  "Access-Control-Max-Age": "86400",
};

const DEFAULT_AES_KEY = "8JVGBahUQ2xE5ZTU";

export default {
  async fetch(request, env, ctx) {
    // 1. Handle CORS Preflight
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: CORS_HEADERS });
    }

    const url = new URL(request.url);
    const target = url.searchParams.get("url") || url.searchParams.get("u");

    if (!target) {
      return new Response(JSON.stringify({ status: 200, message: "Disha Pro Cloudflare Edge Streamer Active" }), {
        status: 200,
        headers: { ...CORS_HEADERS, "Content-Type": "application/json" }
      });
    }

    // Block dummy placeholder links
    if (target.includes("pdflink.com") || target.includes("videolink.com")) {
      return new Response(
        `<!DOCTYPE html><html><head><meta charset="utf-8"><title>नोट्स उपलब्ध नहीं हैं</title>
        <style>body{background:#0a0a0c;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;text-align:center;}</style>
        </head><body><div>
        <h2 style="color:#f59e0b;font-size:22px;margin-bottom:8px;">⚠️ नोट्स उपलब्ध नहीं हैं</h2>
        <p style="color:#a1a1aa;font-size:14px;max-width:380px;line-height:1.6;">इस क्लास के लिए अभी कोई PDF नोट्स अपलोड नहीं किए गए हैं।</p>
        <button onclick="window.close()" style="margin-top:16px;padding:8px 20px;border-radius:8px;border:none;background:#27272a;color:#fff;cursor:pointer;font-weight:bold;">वापस जाएं</button>
        </div></body></html>`,
        { status: 404, headers: { ...CORS_HEADERS, "Content-Type": "text/html; charset=utf-8" } }
      );
    }

    try {
      const upstreamHeaders = new Headers();
      upstreamHeaders.set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36");
      upstreamHeaders.set("Referer", "https://dishaonlineclasses.classx.co.in/");
      upstreamHeaders.set("Origin", "https://dishaonlineclasses.classx.co.in");
      upstreamHeaders.set("Accept", "*/*");

      const rangeHeader = request.headers.get("Range");
      if (rangeHeader) {
        upstreamHeaders.set("Range", rangeHeader);
      }

      const upstreamRes = await fetch(target, {
        method: "GET",
        headers: upstreamHeaders,
        redirect: "follow",
      });

      // If upstream is 404/not found
      if (upstreamRes.status === 404 || upstreamRes.status === 403) {
        const isPdfTarget = target.toLowerCase().includes(".pdf");
        if (isPdfTarget) {
          return new Response(
            `<!DOCTYPE html><html><head><meta charset="utf-8"><title>फाइल सर्वर पर नहीं मिली</title>
            <style>body{background:#0a0a0c;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;text-align:center;}</style>
            </head><body><div>
            <h2 style="color:#ef4444;font-size:22px;margin-bottom:8px;">⚠️ PDF फाइल सर्वर पर नहीं मिली</h2>
            <p style="color:#a1a1aa;font-size:14px;max-width:380px;line-height:1.6;">यह फाइल दिशा ऑनलाइन क्लासेज के सर्वर पर अभी उपलब्ध नहीं है।</p>
            <button onclick="window.close()" style="margin-top:16px;padding:8px 20px;border-radius:8px;border:none;background:#27272a;color:#fff;cursor:pointer;font-weight:bold;">वापस जाएं</button>
            </div></body></html>`,
            { status: 404, headers: { ...CORS_HEADERS, "Content-Type": "text/html; charset=utf-8" } }
          );
        }
      }

      const contentType = (upstreamRes.headers.get("content-type") || "").toLowerCase();
      const isM3u8 = target.includes(".m3u8") || contentType.includes("mpegurl") || contentType.includes("application/x-mpegurl");
      const isPdf = target.toLowerCase().includes(".pdf") || contentType.includes("application/pdf");

      // ==========================================
      // A. PDF File Handler (With Auto XOR Decrypt)
      // ==========================================
      if (isPdf) {
        const rawBuf = await upstreamRes.arrayBuffer();
        const bytes = new Uint8Array(rawBuf);

        // Auto-detect XOR encryption: If magic bytes are NOT "%PDF" (0x25, 0x50, 0x44, 0x46)
        if (bytes.length >= 4 && (bytes[0] !== 0x25 || bytes[1] !== 0x50 || bytes[2] !== 0x44 || bytes[3] !== 0x46)) {
          const keyStr = url.searchParams.get("k") || DEFAULT_AES_KEY;
          const keyBytes = new TextEncoder().encode(keyStr);
          const limit = Math.min(28, bytes.length);
          for (let i = 0; i < limit; i++) {
            const mask = i < keyBytes.length ? keyBytes[i] : i;
            bytes[i] = (bytes[i] ^ mask) & 0xff;
          }
        }

        const outHeaders = new Headers();
        Object.entries(CORS_HEADERS).forEach(([k, v]) => outHeaders.set(k, v));
        outHeaders.set("Content-Type", "application/pdf");
        outHeaders.set("Content-Disposition", "inline; filename=\"disha-class-notes.pdf\"");
        outHeaders.set("Cache-Control", "public, max-age=86400");

        return new Response(bytes, {
          status: 200,
          headers: outHeaders,
        });
      }

      // ==========================================
      // B. HLS Playlist Handler (.m3u8)
      // ==========================================
      if (isM3u8) {
        const text = await upstreamRes.text();
        const baseTarget = target.substring(0, target.lastIndexOf("/") + 1);

        const rewritten = text.split("\n").map(line => {
          const trimmed = line.trim();
          if (!trimmed) return line;

          // Rewrite URI inside #EXT-X-KEY
          if (trimmed.startsWith("#EXT-X-KEY")) {
            return trimmed.replace(/URI="([^"]+)"/, (match, uri) => {
              const fullKeyUrl = uri.startsWith("http") ? uri : new URL(uri, baseTarget).href;
              return `URI="${url.origin}/?url=${encodeURIComponent(fullKeyUrl)}"`;
            });
          }

          // Rewrite segment URLs
          if (!trimmed.startsWith("#")) {
            const fullSegUrl = trimmed.startsWith("http") ? trimmed : new URL(trimmed, baseTarget).href;
            return `${url.origin}/?url=${encodeURIComponent(fullSegUrl)}`;
          }

          return line;
        }).join("\n");

        const outHeaders = new Headers();
        Object.entries(CORS_HEADERS).forEach(([k, v]) => outHeaders.set(k, v));
        outHeaders.set("Content-Type", "application/vnd.apple.mpegurl");
        outHeaders.set("Cache-Control", "no-cache");

        return new Response(rewritten, {
          status: 200,
          headers: outHeaders,
        });
      }

      // ==========================================
      // C. Video Segments (.ts, .mp4, etc.)
      // ==========================================
      const outHeaders = new Headers(upstreamRes.headers);
      Object.entries(CORS_HEADERS).forEach(([k, v]) => outHeaders.set(k, v));
      outHeaders.set("Cache-Control", "public, max-age=86400");

      return new Response(upstreamRes.body, {
        status: upstreamRes.status,
        headers: outHeaders,
      });

    } catch (err) {
      return new Response(JSON.stringify({ error: err.message }), {
        status: 500,
        headers: { ...CORS_HEADERS, "Content-Type": "application/json" }
      });
    }
  }
};
