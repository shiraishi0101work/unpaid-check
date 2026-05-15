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


@app.route("/generate", methods=["POST"])
def generate():
    data = request.get_json()
    text      = (data.get("text") or "").strip()
    color_hex = data.get("color", "#FF88BB")
    font_size = int(data.get("font_size", 200))

    if not text:
        return jsonify({"error": "テキストを入力してください"}), 400

    font_size = max(60, min(600, font_size))

    try:
        img = generate_sticker(text, color_hex=color_hex, font_size=font_size)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    # ファイル保存（ダウンロード用）
    filename = f"sticker_{uuid.uuid4().hex[:8]}.png"
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
