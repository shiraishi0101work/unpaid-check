import os
import subprocess
import json
import config


def get_video_duration(video_path):
    """動画の長さを取得"""
    cmd = [
        config.FFPROBE_PATH,
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        video_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    data = json.loads(result.stdout)
    return float(data["format"]["duration"])


def extract_clip(video_path, start, end, output_path, precise=True):
    """動画から指定範囲を切り出し"""
    # パディング追加
    padded_start = max(0, start - config.CLIP_PADDING_BEFORE)
    duration_limit = get_video_duration(video_path)
    padded_end = min(duration_limit, end + config.CLIP_PADDING_AFTER)

    duration = padded_end - padded_start

    if precise:
        # 精密カット（再エンコード）
        cmd = [
            config.FFMPEG_PATH,
            "-y",
            "-ss", str(padded_start),
            "-i", video_path,
            "-t", str(duration),
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "20",
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart",
            output_path,
        ]
    else:
        # 高速カット（キーフレーム単位）
        cmd = [
            config.FFMPEG_PATH,
            "-y",
            "-ss", str(padded_start),
            "-i", video_path,
            "-t", str(duration),
            "-c", "copy",
            "-movflags", "+faststart",
            output_path,
        ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpegエラー: {result.stderr}")

    return output_path


def extract_clips_batch(video_path, clips, video_id):
    """複数クリップを一括抽出"""
    results = []
    for i, clip in enumerate(clips):
        filename = f"{video_id}_clip_{i+1:03d}.mp4"
        output_path = os.path.join(config.CLIPS_DIR, filename)

        extract_clip(
            video_path,
            clip["start_time"],
            clip["end_time"],
            output_path,
        )

        results.append({
            "index": i + 1,
            "title": clip.get("title", f"クリップ {i+1}"),
            "filename": filename,
            "path": output_path,
            "start": clip["start_time"],
            "end": clip["end_time"],
        })

    return results
