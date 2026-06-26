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
