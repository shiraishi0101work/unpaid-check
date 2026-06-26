import os
import json
import subprocess
import config
from subtitle_gen import seconds_to_ass_time


def export_with_overlays(clip_path, subtitles, overlays, format_type, video_id, clip_index):
    """字幕・オーバーレイ画像・エフェクトを合成して最終動画を出力"""
    base_name = f"{video_id}_clip_{clip_index:03d}_final"
    output_filename = f"{base_name}.mp4"
    output_path = os.path.join(config.OUTPUT_DIR, output_filename)

    # ASS字幕を生成
    ass_path = os.path.join(config.CLIPS_DIR, f"{base_name}.ass")
    _generate_edited_ass(subtitles, format_type, ass_path)

    # フィルターグラフ構築
    cmd = [config.FFMPEG_PATH, "-y", "-i", clip_path]

    # オーバーレイ画像入力を追加
    image_overlays = [o for o in overlays if o.get("type") == "image" and o.get("file_path")]
    for img in image_overlays:
        if os.path.exists(img["file_path"]):
            cmd.extend(["-i", img["file_path"]])

    filter_parts = []
    current_label = "0:v"

    # フォーマット変換
    if format_type == "vertical":
        filter_parts.append(
            f"[{current_label}]scale=1080:1920:force_original_aspect_ratio=increase,"
            f"crop=1080:1920,boxblur=25[bg];"
            f"[0:v]scale=1080:-2[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2[formatted]"
        )
        current_label = "formatted"
    else:
        filter_parts.append(
            f"[{current_label}]scale=1920:1080:force_original_aspect_ratio=decrease,"
            f"pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black[formatted]"
        )
        current_label = "formatted"

    # 画像オーバーレイを追加
    for i, img in enumerate(image_overlays):
        input_idx = i + 1
        x = img.get("x", "50")
        y = img.get("y", "50")
        size = int(img.get("size", 15))
        start = float(img.get("start_time", 0))
        end = float(img.get("end_time", 9999))

        # 位置計算（%からピクセル）
        if format_type == "vertical":
            w, h = 1080, 1920
        else:
            w, h = 1920, 1080

        scale_w = int(w * size / 100)
        x_px = int(float(x) / 100 * w - scale_w / 2)
        y_px = int(float(y) / 100 * h - scale_w / 2)

        next_label = f"ov{i}"
        filter_parts.append(
            f"[{input_idx}:v]scale={scale_w}:-1[img{i}];"
            f"[{current_label}][img{i}]overlay={x_px}:{y_px}"
            f":enable='between(t,{start},{end})'[{next_label}]"
        )
        current_label = next_label

    # 字幕オーバーレイ
    escaped_ass = ass_path.replace("\\", "/").replace(":", "\\:")
    next_label = "subtitled"
    filter_parts.append(
        f"[{current_label}]ass='{escaped_ass}'[{next_label}]"
    )
    current_label = next_label

    # フェードイン
    final_label = "out"
    filter_parts.append(
        f"[{current_label}]fade=t=in:st=0:d=0.5[{final_label}]"
    )

    filter_complex = ";".join(filter_parts)

    cmd.extend([
        "-filter_complex", filter_complex,
        "-map", f"[{final_label}]",
        "-map", "0:a?",
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
        # フォールバック: シンプル版
        return _export_simple(clip_path, ass_path, format_type, output_path)

    # 一時ファイル削除
    if os.path.exists(ass_path):
        os.remove(ass_path)

    return {"filename": output_filename, "path": output_path}


def _export_simple(clip_path, ass_path, format_type, output_path):
    """シンプルなエクスポート（字幕のみ）"""
    if format_type == "vertical":
        vf = (
            "scale=1080:1920:force_original_aspect_ratio=increase,"
            "crop=1080:1920,"
            f"ass='{ass_path.replace(chr(92), '/').replace(':', chr(92) + ':')}',"
            "fade=t=in:st=0:d=0.5"
        )
    else:
        vf = (
            "scale=1920:1080:force_original_aspect_ratio=decrease,"
            "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black,"
            f"ass='{ass_path.replace(chr(92), '/').replace(':', chr(92) + ':')}',"
            "fade=t=in:st=0:d=0.5"
        )

    cmd = [
        config.FFMPEG_PATH, "-y",
        "-i", clip_path,
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"エクスポートエラー: {result.stderr}")

    if os.path.exists(ass_path):
        os.remove(ass_path)

    return {"filename": os.path.basename(output_path), "path": output_path}


def _generate_edited_ass(subtitles, format_type, output_path):
    """編集済み字幕からASSファイルを生成"""
    if format_type == "vertical":
        res_x, res_y = 1080, 1920
        default_margin_v = 120
    else:
        res_x, res_y = 1920, 1080
        default_margin_v = 60

    font_name = "Noto Sans JP Bold"
    font_file = os.path.join(config.FONTS_DIR, "NotoSansJP-Bold.otf")
    if not os.path.exists(font_file):
        font_name = "MS Gothic"

    # スタイル定義を構築
    styles_section = []
    style_defs = {}

    for sub in subtitles:
        style_name = sub.get("style_name", "Default")
        if style_name in style_defs:
            continue

        font_size = sub.get("font_size", 48)
        color = sub.get("color", "#FFFFFF")
        outline_color = sub.get("outline_color", "#000000")
        outline_width = sub.get("outline_width", 3)
        bold = -1 if sub.get("bold", True) else 0
        alignment = _position_to_alignment(sub.get("position", "bottom"))
        margin_v = sub.get("margin_v", default_margin_v)
        bg_color = sub.get("background_color", "&H80000000")

        # ASSカラー変換（#RRGGBBを&H00BBGGRRに）
        ass_color = _hex_to_ass_color(color)
        ass_outline = _hex_to_ass_color(outline_color)

        style_line = (
            f"Style: {style_name},{font_name},{font_size},{ass_color},&H000000FF,"
            f"{ass_outline},{bg_color},{bold},0,0,0,100,100,0,0,1,"
            f"{outline_width},2,{alignment},30,30,{margin_v},1"
        )
        styles_section.append(style_line)
        style_defs[style_name] = True

    if not styles_section:
        styles_section.append(
            f"Style: Default,{font_name},48,&H00FFFFFF,&H000000FF,"
            f"&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,2,2,30,30,{default_margin_v},1"
        )

    header = f"""[Script Info]
Title: Edited Subtitles
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709
PlayResX: {res_x}
PlayResY: {res_y}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
{chr(10).join(styles_section)}

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    events = []
    for sub in subtitles:
        start_tc = seconds_to_ass_time(float(sub.get("start", 0)))
        end_tc = seconds_to_ass_time(float(sub.get("end", 0)))
        text = sub.get("text", "").replace("\n", "\\N")
        style_name = sub.get("style_name", "Default")

        events.append(f"Dialogue: 0,{start_tc},{end_tc},{style_name},,0,0,0,,{text}")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(header + "\n".join(events) + "\n")


def _hex_to_ass_color(hex_color):
    """#RRGGBB を ASS形式 &H00BBGGRR に変換"""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 6:
        r, g, b = hex_color[0:2], hex_color[2:4], hex_color[4:6]
        return f"&H00{b}{g}{r}"
    return "&H00FFFFFF"


def _position_to_alignment(position):
    """位置をASSアライメント番号に変換"""
    return {
        "top-left": 7, "top": 8, "top-right": 9,
        "center-left": 4, "center": 5, "center-right": 6,
        "bottom-left": 1, "bottom": 2, "bottom-right": 3,
    }.get(position, 2)
