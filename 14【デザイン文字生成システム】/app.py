"""
デザイン文字生成システム - Flask Web アプリ
"""

import os
import uuid
import io
import base64
from flask import Flask, render_template, request, jsonify, send_file
from generator import generate_sticker, get_available_fonts

app = Flask(__name__)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/fonts")
def fonts():
    return jsonify(get_available_fonts())


@app.route("/generate", methods=["POST"])
def generate():
    data = request.get_json()
    text      = (data.get("text") or "").strip()
    color_hex = data.get("color", "#FF88BB")
    font_size = int(data.get("font_size", 200))
    font_id         = data.get("font_id") or None
    border_mode     = data.get("border_mode", "double")
    border_color1   = data.get("border_color1", "#1a1a1a")
    border_color2   = data.get("border_color2", "#ffffff")
    border_size     = int(data.get("border_size", 5))
    letter_spacing  = int(data.get("letter_spacing", 0))
    x_scale         = int(data.get("x_scale", 100))
    slant           = int(data.get("slant", 0))
    fake_bold       = int(data.get("fake_bold", 0))
    font_weight     = data.get("font_weight")
    font_weight     = int(font_weight) if font_weight is not None else None
    gloss           = bool(data.get("gloss", True))
    gloss_intensity = int(data.get("gloss_intensity", 60))
    gradient_mode   = data.get("gradient_mode", "none")
    gradient_color2 = data.get("gradient_color2") or None

    if not text:
        return jsonify({"error": "テキストを入力してください"}), 400

    font_size   = max(60, min(600, font_size))
    border_size = max(1, min(10, border_size))

    try:
        img = generate_sticker(
            text,
            color_hex=color_hex,
            font_size=font_size,
            font_id=font_id,
            border_mode=border_mode,
            border_color1=border_color1,
            border_color2=border_color2,
            border_size=border_size,
            letter_spacing=letter_spacing,
            x_scale=x_scale,
            slant=slant,
            fake_bold=fake_bold,
            font_weight=font_weight,
            gloss=gloss,
            gloss_intensity=gloss_intensity,
            gradient_mode=gradient_mode,
            gradient_color2=gradient_color2,
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    # ファイル保存（ダウンロード用）
    safe_text = "".join(c for c in text if c.isalnum() or "\u3000" <= c <= "\u9fff" or "\u3040" <= c <= "\u30ff")[:20]
    filename = f"{safe_text}_{uuid.uuid4().hex[:6]}.png"
    filepath = os.path.join(OUTPUT_DIR, filename)
    img.save(filepath, "PNG")

    # プレビュー用 Base64
    buf = io.BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode("utf-8")

    return jsonify({
        "image_data": f"data:image/png;base64,{b64}",
        "filename": filename,
        "width": img.width,
        "height": img.height,
    })


@app.route("/download/<filename>")
def download(filename):
    # パストラバーサル対策
    filename = os.path.basename(filename)
    filepath = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(filepath):
        return "ファイルが見つかりません", 404
    return send_file(filepath, as_attachment=True, download_name=filename)


if __name__ == "__main__":
    print("デザイン文字生成システム起動中...")
    print("ブラウザで http://localhost:5050 を開いてください")
    app.run(debug=True, port=5050)
