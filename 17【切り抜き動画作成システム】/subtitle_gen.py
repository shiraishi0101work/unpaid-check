import os
import config


def seconds_to_ass_time(seconds):
    """秒をASS形式タイムコード(H:MM:SS.CC)に変換"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def generate_ass_subtitles(transcript_segment, clip_start, clip_end, style="default", font_size=48):
    """ASS形式の字幕ファイルを生成"""

    # フォントパス確認
    font_name = "Noto Sans JP Bold"
    font_file = os.path.join(config.FONTS_DIR, "NotoSansJP-Bold.otf")
    if not os.path.exists(font_file):
        font_name = "MS Gothic"

    styles = {
        "default": {
            "fontsize": font_size,
            "primary_color": "&H00FFFFFF",   # 白
            "outline_color": "&H00000000",   # 黒アウトライン
            "back_color": "&H80000000",      # 半透明黒
            "outline": 3,
            "shadow": 2,
            "alignment": 2,  # 下中央
            "margin_v": 60,
        },
        "vertical": {
            "fontsize": int(font_size * 0.85),
            "primary_color": "&H00FFFFFF",
            "outline_color": "&H00000000",
            "back_color": "&H80000000",
            "outline": 3,
            "shadow": 2,
            "alignment": 2,  # 下中央
            "margin_v": 120,
        },
        "impact": {
            "fontsize": int(font_size * 1.3),
            "primary_color": "&H0000FFFF",   # 黄色
            "outline_color": "&H00000000",
            "back_color": "&H80000000",
            "outline": 4,
            "shadow": 3,
            "alignment": 5,  # 中央
            "margin_v": 0,
        },
    }

    s = styles.get(style, styles["default"])

    header = f"""[Script Info]
Title: Auto Generated Subtitles
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{s['fontsize']},{s['primary_color']},&H000000FF,{s['outline_color']},{s['back_color']},-1,0,0,0,100,100,0,0,1,{s['outline']},{s['shadow']},{s['alignment']},30,30,{s['margin_v']},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    events = []
    for entry in transcript_segment:
        entry_start = entry["start"]
        entry_end = entry_start + entry["duration"]

        # クリップ範囲内のみ
        if entry_end < clip_start or entry_start > clip_end:
            continue

        # クリップ開始時刻を基準にオフセット
        rel_start = max(0, entry_start - clip_start)
        rel_end = entry_end - clip_start

        start_tc = seconds_to_ass_time(rel_start)
        end_tc = seconds_to_ass_time(rel_end)
        text = entry["text"].replace("\n", "\\N")

        events.append(f"Dialogue: 0,{start_tc},{end_tc},Default,,0,0,0,,{text}")

    return header + "\n".join(events) + "\n"


def save_subtitles(ass_content, output_path):
    """字幕ファイルを保存"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(ass_content)
    return output_path
