import os
import subprocess
import config
from subtitle_gen import generate_ass_subtitles, save_subtitles
from transcript import get_transcript_chunk


def auto_edit_clip(clip_path, transcript, clip_start, clip_end,
                   format_type="horizontal", effects=None, video_id="clip"):
    """クリップを自動編集"""
    if effects is None:
        effects = {
            "subtitles": True,
            "zoom": False,
            "fade": True,
            "blur_bg": True,
        }

    base_name = os.path.splitext(os.path.basename(clip_path))[0]
    output_filename = f"{base_name}_{format_type}_edited.mp4"
    output_path = os.path.join(config.OUTPUT_DIR, output_filename)

    # 字幕ファイル生成
    subtitle_path = None
    if effects.get("subtitles") and transcript:
        segment = get_transcript_chunk(transcript, clip_start, clip_end)
        if segment:
            style = "vertical" if format_type == "vertical" else "default"
            ass_content = generate_ass_subtitles(segment, clip_start, clip_end, style=style)
            subtitle_path = os.path.join(config.CLIPS_DIR, f"{base_name}.ass")
            save_subtitles(ass_content, subtitle_path)

    # FFmpegフィルターグラフ構築
    filters = build_filter_graph(format_type, subtitle_path, effects)

    cmd = [
        config.FFMPEG_PATH,
        "-y",
        "-i", clip_path,
    ]

    if filters:
        cmd.extend(["-vf", filters])

    cmd.extend([
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "20",
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",
        output_path,
    ])

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"編集エラー: {result.stderr}")

    # 一時字幕ファイル削除
    if subtitle_path and os.path.exists(subtitle_path):
        os.remove(subtitle_path)

    return {
        "filename": output_filename,
        "path": output_path,
        "format": format_type,
    }


def build_filter_graph(format_type, subtitle_path, effects):
    """FFmpegフィルターグラフを構築"""
    filters = []

    if format_type == "vertical":
        if effects.get("blur_bg"):
            # ブラー背景 + メインコンテンツのオーバーレイ
            # 複合フィルターは-filter_complexで処理が必要なので、
            # ここではシンプルなクロップ方式を使う
            filters.append("scale=1080:1920:force_original_aspect_ratio=decrease")
            filters.append("pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black")
        else:
            # 中央クロップ
            filters.append("crop=ih*9/16:ih")
            filters.append("scale=1080:1920")
    else:
        # 横型: 1920x1080に統一
        filters.append("scale=1920:1080:force_original_aspect_ratio=decrease")
        filters.append("pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black")

    # ズームエフェクト
    if effects.get("zoom"):
        filters.append("zoompan=z='min(zoom+0.0005,1.08)':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1920x1080")

    # 字幕オーバーレイ
    if subtitle_path and effects.get("subtitles"):
        # Windows用にパスのバックスラッシュをエスケープ
        escaped_path = subtitle_path.replace("\\", "/").replace(":", "\\:")
        filters.append(f"ass='{escaped_path}'")

    # フェードイン・アウト
    if effects.get("fade"):
        filters.append("fade=t=in:st=0:d=0.5")
        # フェードアウトは動画長が必要なので後で追加する場合がある

    return ",".join(filters) if filters else None


def auto_edit_vertical_with_blur(clip_path, transcript, clip_start, clip_end,
                                  effects=None, video_id="clip"):
    """ブラー背景付き縦型動画を生成（filter_complex使用）"""
    if effects is None:
        effects = {"subtitles": True, "fade": True}

    base_name = os.path.splitext(os.path.basename(clip_path))[0]
    output_filename = f"{base_name}_vertical_blur_edited.mp4"
    output_path = os.path.join(config.OUTPUT_DIR, output_filename)

    # 字幕ファイル生成
    subtitle_path = None
    if effects.get("subtitles") and transcript:
        segment = get_transcript_chunk(transcript, clip_start, clip_end)
        if segment:
            ass_content = generate_ass_subtitles(segment, clip_start, clip_end, style="vertical")
            subtitle_path = os.path.join(config.CLIPS_DIR, f"{base_name}_vert.ass")
            save_subtitles(ass_content, subtitle_path)

    # filter_complex: 背景ブラー + メインコンテンツオーバーレイ
    filter_complex = (
        "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=25[bg];"
        "[0:v]scale=1080:-2[fg];"
        "[bg][fg]overlay=(W-w)/2:(H-h)/2"
    )

    if subtitle_path:
        escaped_path = subtitle_path.replace("\\", "/").replace(":", "\\:")
        filter_complex += f",ass='{escaped_path}'"

    if effects.get("fade"):
        filter_complex += ",fade=t=in:st=0:d=0.5"

    filter_complex += "[out]"

    cmd = [
        config.FFMPEG_PATH,
        "-y",
        "-i", clip_path,
        "-filter_complex", filter_complex,
        "-map", "[out]",
        "-map", "0:a?",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "20",
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"縦型編集エラー: {result.stderr}")

    if subtitle_path and os.path.exists(subtitle_path):
        os.remove(subtitle_path)

    return {
        "filename": output_filename,
        "path": output_path,
        "format": "vertical_blur",
    }
