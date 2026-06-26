import os
import yt_dlp
import config


def get_video_info(url):
    """メタデータのみ取得（ダウンロードなし）"""
    opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)

    return {
        "video_id": info.get("id"),
        "title": info.get("title"),
        "duration": info.get("duration"),
        "thumbnail": info.get("thumbnail"),
        "channel": info.get("channel") or info.get("uploader"),
        "upload_date": info.get("upload_date"),
        "view_count": info.get("view_count"),
    }


def download_video(url, progress_callback=None):
    """動画をダウンロード"""
    info = get_video_info(url)
    video_id = info["video_id"]
    output_path = os.path.join(config.DOWNLOADS_DIR, f"{video_id}.%(ext)s")

    existing = [
        f for f in os.listdir(config.DOWNLOADS_DIR)
        if f.startswith(video_id) and not f.endswith(".part")
    ]
    if existing:
        info["video_path"] = os.path.join(config.DOWNLOADS_DIR, existing[0])
        return info

    def hook(d):
        if progress_callback and d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes", 0)
            if total > 0:
                progress_callback(downloaded / total * 100)

    opts = {
        "format": f"bestvideo[height<={config.MAX_VIDEO_HEIGHT}]+bestaudio/best[height<={config.MAX_VIDEO_HEIGHT}]",
        "outtmpl": output_path,
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [hook] if progress_callback else [],
    }

    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])

    downloaded = [
        f for f in os.listdir(config.DOWNLOADS_DIR)
        if f.startswith(video_id) and not f.endswith(".part")
    ]
    if downloaded:
        info["video_path"] = os.path.join(config.DOWNLOADS_DIR, downloaded[0])
    else:
        raise RuntimeError("ダウンロードに失敗しました")

    return info
