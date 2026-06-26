import os
import uuid
import threading
from flask import Flask, render_template, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
import config
from downloader import get_video_info, download_video
from transcript import get_transcript
from comments import get_comments
from analyzer import analyze_highlights, generate_timestamp_text
from clipper import extract_clip, extract_clips_batch
from editor import auto_edit_clip, auto_edit_vertical_with_blur
from ai_style import analyze_reference_style, suggest_decorations, get_default_style
from overlay_export import export_with_overlays

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50MB

UPLOADS_DIR = os.path.join(config.BASE_DIR, "uploads")
REFERENCES_DIR = os.path.join(config.BASE_DIR, "references")
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(REFERENCES_DIR, exist_ok=True)

# ジョブ管理（インメモリ）
jobs = {}
# スタイル設定キャッシュ
current_style = get_default_style()


def create_job():
    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {
        "status": "pending",
        "progress": 0,
        "message": "",
        "result": None,
        "error": None,
    }
    return job_id


def update_job(job_id, **kwargs):
    if job_id in jobs:
        jobs[job_id].update(kwargs)


# ========================
# ルート
# ========================

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    """YouTube URLを分析してハイライトを返す"""
    data = request.get_json()
    url = data.get("url", "").strip()

    if not url:
        return jsonify({"error": "URLを入力してください"}), 400

    job_id = create_job()

    def run():
        try:
            update_job(job_id, status="running", progress=10, message="動画情報を取得中...")
            info = get_video_info(url)

            update_job(job_id, progress=30, message="字幕を取得中...")
            transcript = get_transcript(info["video_id"])

            update_job(job_id, progress=50, message="コメントを取得中...")
            comments = get_comments(info["video_id"])

            update_job(job_id, progress=70, message="AIがハイライトを分析中...")
            highlights = analyze_highlights(
                transcript, comments,
                info["title"], info["duration"]
            )

            timestamp_text = generate_timestamp_text(highlights)

            update_job(job_id, status="completed", progress=100,
                       message="分析完了",
                       result={
                           "video_info": info,
                           "highlights": highlights,
                           "timestamp_text": timestamp_text,
                           "transcript_available": len(transcript) > 0,
                           "comments_count": len(comments),
                       })

        except Exception as e:
            update_job(job_id, status="error", error=str(e))

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"job_id": job_id})


@app.route("/api/download", methods=["POST"])
def api_download():
    """動画をダウンロード"""
    data = request.get_json()
    url = data.get("url", "").strip()

    if not url:
        return jsonify({"error": "URLを入力してください"}), 400

    job_id = create_job()

    def run():
        try:
            def progress_cb(pct):
                update_job(job_id, progress=int(pct), message=f"ダウンロード中... {int(pct)}%")

            update_job(job_id, status="running", progress=0, message="ダウンロード開始...")
            info = download_video(url, progress_callback=progress_cb)

            update_job(job_id, status="completed", progress=100,
                       message="ダウンロード完了",
                       result={
                           "video_id": info["video_id"],
                           "video_path": info["video_path"],
                           "title": info["title"],
                       })

        except Exception as e:
            update_job(job_id, status="error", error=str(e))

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"job_id": job_id})


@app.route("/api/extract", methods=["POST"])
def api_extract():
    """選択されたクリップを抽出・編集"""
    data = request.get_json()
    video_id = data.get("video_id")
    clips = data.get("clips", [])
    format_type = data.get("format", "horizontal")
    effects = data.get("effects", {
        "subtitles": True,
        "zoom": False,
        "fade": True,
        "blur_bg": True,
    })
    url = data.get("url", "")

    if not video_id or not clips:
        return jsonify({"error": "クリップを選択してください"}), 400

    job_id = create_job()

    def run():
        try:
            # 動画ファイルを探す
            video_files = [
                f for f in os.listdir(config.DOWNLOADS_DIR)
                if f.startswith(video_id) and not f.endswith(".part")
            ]
            if not video_files:
                update_job(job_id, status="running", progress=5, message="動画をダウンロード中...")
                info = download_video(url)
                video_path = info["video_path"]
            else:
                video_path = os.path.join(config.DOWNLOADS_DIR, video_files[0])

            # トランスクリプト取得（字幕用）
            transcript = []
            if effects.get("subtitles"):
                update_job(job_id, progress=10, message="字幕データを取得中...")
                transcript = get_transcript(video_id)

            total = len(clips)
            results = []

            for i, clip in enumerate(clips):
                pct_base = 15 + int(i / total * 70)

                # クリップ抽出
                update_job(job_id, status="running", progress=pct_base,
                           message=f"クリップ抽出中 ({i+1}/{total}): {clip.get('title', '')}")

                clip_filename = f"{video_id}_clip_{i+1:03d}.mp4"
                clip_path = os.path.join(config.CLIPS_DIR, clip_filename)

                extract_clip(video_path, clip["start_time"], clip["end_time"], clip_path)

                # 自動編集
                update_job(job_id, progress=pct_base + 5,
                           message=f"編集中 ({i+1}/{total}): {clip.get('title', '')}")

                if format_type == "vertical" and effects.get("blur_bg"):
                    edited = auto_edit_vertical_with_blur(
                        clip_path, transcript,
                        clip["start_time"], clip["end_time"],
                        effects=effects, video_id=video_id,
                    )
                else:
                    edited = auto_edit_clip(
                        clip_path, transcript,
                        clip["start_time"], clip["end_time"],
                        format_type=format_type, effects=effects,
                        video_id=video_id,
                    )

                results.append({
                    "index": i + 1,
                    "title": clip.get("title", f"クリップ {i+1}"),
                    "filename": edited["filename"],
                    "format": edited["format"],
                    "start_display": clip.get("start_display", ""),
                    "end_display": clip.get("end_display", ""),
                })

            update_job(job_id, status="completed", progress=100,
                       message=f"{total}個のクリップ編集完了",
                       result={"clips": results})

        except Exception as e:
            update_job(job_id, status="error", error=str(e))

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"job_id": job_id})


@app.route("/api/status/<job_id>")
def api_status(job_id):
    """ジョブステータスを確認"""
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "ジョブが見つかりません"}), 404
    return jsonify(job)


@app.route("/api/clips/<filename>")
def serve_clip(filename):
    """編集済みクリップを配信"""
    # outputフォルダを優先、なければclipsフォルダ
    if os.path.exists(os.path.join(config.OUTPUT_DIR, filename)):
        return send_from_directory(config.OUTPUT_DIR, filename)
    return send_from_directory(config.CLIPS_DIR, filename)


@app.route("/api/cleanup/<video_id>", methods=["DELETE"])
def api_cleanup(video_id):
    """一時ファイルを削除"""
    count = 0
    for folder in [config.DOWNLOADS_DIR, config.CLIPS_DIR]:
        for f in os.listdir(folder):
            if f.startswith(video_id):
                os.remove(os.path.join(folder, f))
                count += 1
    return jsonify({"deleted": count})


# ========================
# エディター用API
# ========================

@app.route("/api/get-subtitles", methods=["POST"])
def api_get_subtitles():
    """クリップの字幕データを取得"""
    data = request.get_json()
    video_id = data.get("video_id")
    clip_start = float(data.get("start_time", 0))
    clip_end = float(data.get("end_time", 0))

    transcript = get_transcript(video_id)
    subtitles = []
    for entry in transcript:
        entry_start = entry["start"]
        entry_end = entry_start + entry["duration"]
        if entry_end < clip_start or entry_start > clip_end:
            continue
        subtitles.append({
            "text": entry["text"],
            "start": round(entry_start - clip_start, 2),
            "end": round(entry_end - clip_start, 2),
            "font_size": 48,
            "color": "#FFFFFF",
            "outline_color": "#000000",
            "outline_width": 3,
            "bold": True,
            "position": "bottom",
            "style_name": "Default",
        })

    return jsonify({"subtitles": subtitles})


@app.route("/api/upload-image", methods=["POST"])
def api_upload_image():
    """画像素材をアップロード"""
    if "file" not in request.files:
        return jsonify({"error": "ファイルが選択されていません"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "ファイル名がありません"}), 400

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in [".png", ".jpg", ".jpeg", ".gif", ".webp"]:
        return jsonify({"error": "対応形式: PNG, JPG, GIF, WebP"}), 400

    filename = f"{uuid.uuid4().hex[:8]}{ext}"
    filepath = os.path.join(UPLOADS_DIR, filename)
    file.save(filepath)

    return jsonify({
        "filename": filename,
        "path": filepath,
        "url": f"/api/uploads/{filename}",
    })


@app.route("/api/uploads/<filename>")
def serve_upload(filename):
    """アップロード画像を配信"""
    return send_from_directory(UPLOADS_DIR, filename)


@app.route("/api/upload-reference", methods=["POST"])
def api_upload_reference():
    """参考画像をアップロードしてスタイル分析"""
    global current_style

    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "ファイルが選択されていません"}), 400

    paths = []
    for file in files[:5]:
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in [".png", ".jpg", ".jpeg", ".gif", ".webp"]:
            continue
        filename = f"ref_{uuid.uuid4().hex[:8]}{ext}"
        filepath = os.path.join(REFERENCES_DIR, filename)
        file.save(filepath)
        paths.append(filepath)

    if not paths:
        return jsonify({"error": "有効な画像がありません"}), 400

    # AIでスタイル分析
    style = analyze_reference_style(paths)
    current_style = style

    return jsonify({"style": style, "files_count": len(paths)})


@app.route("/api/get-style")
def api_get_style():
    """現在のスタイル設定を取得"""
    return jsonify({"style": current_style})


@app.route("/api/suggest-decorations", methods=["POST"])
def api_suggest_decorations():
    """AIが装飾配置を提案"""
    data = request.get_json()
    transcript_text = data.get("transcript_text", "")
    available_images = data.get("images", [])

    suggestions = suggest_decorations(transcript_text, current_style, available_images)
    return jsonify({"suggestions": suggestions})


@app.route("/api/export", methods=["POST"])
def api_export():
    """編集内容を反映して最終エクスポート"""
    data = request.get_json()
    video_id = data.get("video_id")
    clip_index = int(data.get("clip_index", 1))
    subtitles = data.get("subtitles", [])
    overlays = data.get("overlays", [])
    format_type = data.get("format", "horizontal")

    # オーバーレイ画像のパスを解決
    for ov in overlays:
        if ov.get("type") == "image" and ov.get("filename"):
            ov["file_path"] = os.path.join(UPLOADS_DIR, ov["filename"])

    # クリップファイルを探す
    clip_filename = f"{video_id}_clip_{clip_index:03d}.mp4"
    clip_path = os.path.join(config.CLIPS_DIR, clip_filename)

    if not os.path.exists(clip_path):
        return jsonify({"error": "クリップファイルが見つかりません"}), 404

    job_id = create_job()

    def run():
        try:
            update_job(job_id, status="running", progress=30, message="エクスポート中...")
            result = export_with_overlays(
                clip_path, subtitles, overlays, format_type, video_id, clip_index
            )
            update_job(job_id, status="completed", progress=100,
                       message="エクスポート完了",
                       result=result)
        except Exception as e:
            update_job(job_id, status="error", error=str(e))

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"job_id": job_id})


if __name__ == "__main__":
    print("=" * 50)
    print("切り抜き動画作成システム")
    print(f"http://localhost:8082")
    print("=" * 50)

    # 環境チェック
    if not config.GEMINI_API_KEY:
        print("[警告] GEMINI_API_KEY が未設定です")
    if not config.YOUTUBE_API_KEY:
        print("[警告] YOUTUBE_API_KEY が未設定です（コメント取得不可）")

    app.run(host="0.0.0.0", port=8082, debug=True)
