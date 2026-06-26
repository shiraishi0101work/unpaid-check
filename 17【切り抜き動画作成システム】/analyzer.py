import json
import google.generativeai as genai
import config
from transcript import format_timestamp, transcript_to_text


def analyze_highlights(transcript, comments, video_title, duration):
    """Gemini APIでハイライトポイントを分析"""
    if not config.GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEYが設定されていません")

    genai.configure(api_key=config.GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-2.0-flash")

    # トランスクリプトをチャンクに分割（長い動画対応）
    chunk_size = 1800  # 30分ごと
    chunks = []
    if transcript:
        current_chunk = []
        chunk_start = 0
        for entry in transcript:
            if entry["start"] - chunk_start > chunk_size and current_chunk:
                chunks.append(current_chunk)
                current_chunk = []
                chunk_start = entry["start"]
            current_chunk.append(entry)
        if current_chunk:
            chunks.append(current_chunk)
    else:
        chunks = [None]

    # コメント要約
    comment_text = ""
    if comments:
        top_comments = comments[:50]
        comment_lines = []
        for c in top_comments:
            ts_info = f" (言及タイムスタンプ: {', '.join(c['timestamp_mentions'])})" if c["timestamp_mentions"] else ""
            comment_lines.append(f"- [いいね{c['likes']}] {c['text'][:200]}{ts_info}")
        comment_text = "\n".join(comment_lines)

    all_highlights = []

    for i, chunk in enumerate(chunks):
        transcript_text = ""
        if chunk:
            transcript_text = transcript_to_text(chunk)

        prompt = f"""あなたはYouTube切り抜き動画の専門家です。
以下の動画のトランスクリプトとコメントを分析し、切り抜き動画として面白いハイライトポイントを特定してください。

# 動画情報
タイトル: {video_title}
総尺: {format_timestamp(duration)}
{f"パート: {i+1}/{len(chunks)}" if len(chunks) > 1 else ""}

# トランスクリプト
{transcript_text if transcript_text else "(トランスクリプトなし - コメントのみで分析)"}

# 視聴者コメント（いいね数順）
{comment_text if comment_text else "(コメントなし)"}

# 分析指示
以下の基準で面白いポイントを5〜15個見つけてください：
1. 笑える瞬間・面白い発言
2. 感動的・エモーショナルな瞬間
3. 議論を呼ぶ発言・炎上ポイント
4. 重要な情報の暴露・サプライズ
5. 名言・印象的なフレーズ
6. コメント欄で多く言及されている瞬間

各ポイントについて、切り抜き動画として成立するように前後の文脈を含めた適切な範囲（最短30秒、最長5分）を指定してください。

# 出力形式（JSON配列のみ出力）
[
  {{
    "start_time": 開始秒数(数値),
    "end_time": 終了秒数(数値),
    "title": "切り抜きタイトル（視聴者が見たくなるような魅力的なタイトル）",
    "reason": "この部分が面白い理由",
    "score": 興味度スコア(1-10の数値),
    "category": "カテゴリ(funny/emotional/controversial/surprise/quote/viral)"
  }}
]

JSON配列のみを出力し、他のテキストは含めないでください。"""

        try:
            response = model.generate_content(prompt)
            text = response.text.strip()

            # JSON部分を抽出
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()

            highlights = json.loads(text)

            # バリデーション
            for h in highlights:
                h["start_time"] = max(0, float(h["start_time"]))
                h["end_time"] = min(duration, float(h["end_time"]))
                h["score"] = max(1, min(10, int(h["score"])))
                if h["end_time"] <= h["start_time"]:
                    h["end_time"] = h["start_time"] + 60

                h["start_display"] = format_timestamp(h["start_time"])
                h["end_display"] = format_timestamp(h["end_time"])
                h["duration_display"] = format_timestamp(h["end_time"] - h["start_time"])

            all_highlights.extend(highlights)

        except Exception as e:
            print(f"Gemini分析エラー (chunk {i+1}): {e}")
            continue

    # スコア順にソート、重複排除
    all_highlights.sort(key=lambda x: x["score"], reverse=True)
    return deduplicate_highlights(all_highlights)


def deduplicate_highlights(highlights, overlap_threshold=0.5):
    """重複するハイライトを除去"""
    result = []
    for h in highlights:
        is_dup = False
        for existing in result:
            overlap_start = max(h["start_time"], existing["start_time"])
            overlap_end = min(h["end_time"], existing["end_time"])
            if overlap_end > overlap_start:
                overlap_duration = overlap_end - overlap_start
                h_duration = h["end_time"] - h["start_time"]
                if overlap_duration / h_duration > overlap_threshold:
                    is_dup = True
                    break
        if not is_dup:
            result.append(h)
    return result


def generate_timestamp_text(highlights):
    """YouTubeコメント用のタイムスタンプテキストを生成"""
    lines = ["【タイムスタンプ】"]
    sorted_highlights = sorted(highlights, key=lambda x: x["start_time"])
    for h in sorted_highlights:
        lines.append(f"{h['start_display']} {h['title']}")
    return "\n".join(lines)
