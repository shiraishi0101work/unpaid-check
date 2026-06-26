import os
import json
import base64
from google import genai
from google.genai import types
import config


def encode_image(image_path):
    """画像をbase64エンコード"""
    with open(image_path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")


def get_mime_type(path):
    ext = os.path.splitext(path)[1].lower()
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }.get(ext, "image/png")


def analyze_reference_style(reference_paths):
    """参考画像/動画スクリーンショットからスタイルを学習"""
    if not config.GEMINI_API_KEY or not reference_paths:
        return get_default_style()

    client = genai.Client(api_key=config.GEMINI_API_KEY)

    # 画像をパーツとして準備
    parts = []
    for path in reference_paths[:5]:  # 最大5枚
        if os.path.exists(path):
            image_data = encode_image(path)
            mime = get_mime_type(path)
            parts.append(types.Part.from_bytes(
                data=base64.standard_b64decode(image_data),
                mime_type=mime,
            ))

    parts.append(types.Part.from_text("""これらはYouTube切り抜き動画のスクリーンショット/参考画像です。
これらの画像から、切り抜き動画の編集スタイルを詳細に分析してください。

以下の項目について、JSON形式で回答してください：

{
  "subtitle_style": {
    "font_size": "フォントサイズ(small/medium/large/xlarge)",
    "font_weight": "太さ(normal/bold)",
    "color": "メインカラー(hex)",
    "outline_color": "アウトラインカラー(hex)",
    "outline_width": "アウトライン太さ(数値1-5)",
    "shadow": "影あり/なし(true/false)",
    "position": "位置(top/center/bottom)",
    "background": "背景あり/なし(true/false)",
    "background_color": "背景色(hex with alpha)",
    "animation": "アニメーション(none/fade/pop/slide)"
  },
  "decoration_style": {
    "use_emoji": "絵文字使用(true/false)",
    "use_effects": "エフェクト画像使用(true/false)",
    "color_scheme": "配色テーマ(colorful/monochrome/warm/cool/neon)",
    "emphasis_method": "強調方法(zoom/shake/flash/highlight)",
    "overall_mood": "全体の雰囲気(casual/serious/energetic/cute)"
  },
  "layout": {
    "subtitle_margin_bottom": "下マージン(%)",
    "decoration_positions": ["装飾の配置傾向(top-left/top-right/bottom-left/bottom-right/center)"],
    "overlay_opacity": "オーバーレイ不透明度(0-100)"
  },
  "suggestions": ["この参考スタイルを再現するための具体的なアドバイス(3-5個)"]
}

JSON形式のみ出力してください。"""))

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=types.Content(parts=parts),
        )
        text = response.text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        return json.loads(text)
    except Exception as e:
        print(f"スタイル分析エラー: {e}")
        return get_default_style()


def suggest_decorations(transcript_text, style, available_images):
    """AIがコンテンツに合った装飾配置を提案"""
    if not config.GEMINI_API_KEY:
        return []

    client = genai.Client(api_key=config.GEMINI_API_KEY)

    image_list = "\n".join([f"- {img['name']}: {img.get('description', '画像素材')}" for img in available_images])

    prompt = f"""あなたはYouTube切り抜き動画の編集者です。
以下の字幕テキストと利用可能な画像素材を見て、適切なタイミングと位置に装飾を配置する提案をしてください。

# 字幕テキスト
{transcript_text}

# スタイル設定
{json.dumps(style, ensure_ascii=False, indent=2)}

# 利用可能な画像素材
{image_list if image_list else "(なし)"}

# 指示
- 面白いポイントや強調したい部分に装飾を配置
- 各装飾の表示タイミング（開始秒・終了秒）と位置を指定
- 感情に合ったエフェクトを提案

JSON配列で出力：
[
  {{
    "type": "image/text/effect",
    "content": "画像ファイル名 or テキスト or エフェクト名",
    "start_time": 開始秒,
    "end_time": 終了秒,
    "position": {{"x": "x位置(%)", "y": "y位置(%)"}},
    "size": "サイズ(%)",
    "animation": "none/fade/pop/bounce/shake",
    "reason": "配置理由"
  }}
]

JSON配列のみ出力してください。"""

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
        )
        text = response.text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        return json.loads(text)
    except Exception as e:
        print(f"装飾提案エラー: {e}")
        return []


def get_default_style():
    """デフォルトスタイル"""
    return {
        "subtitle_style": {
            "font_size": "large",
            "font_weight": "bold",
            "color": "#FFFFFF",
            "outline_color": "#000000",
            "outline_width": 3,
            "shadow": True,
            "position": "bottom",
            "background": False,
            "background_color": "#00000080",
            "animation": "none",
        },
        "decoration_style": {
            "use_emoji": True,
            "use_effects": True,
            "color_scheme": "colorful",
            "emphasis_method": "zoom",
            "overall_mood": "energetic",
        },
        "layout": {
            "subtitle_margin_bottom": "10",
            "decoration_positions": ["top-right", "bottom-left"],
            "overlay_opacity": 90,
        },
        "suggestions": [
            "大きめの白文字に黒アウトラインが定番",
            "感情的な場面ではテキストサイズを大きく",
            "面白い場面にはリアクション画像を右上に配置",
        ],
    }
