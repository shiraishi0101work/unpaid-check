from youtube_transcript_api import YouTubeTranscriptApi


def get_transcript(video_id, lang="ja"):
    """YouTube字幕（トランスクリプト）を取得"""
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

        # 手動字幕を優先
        try:
            transcript = transcript_list.find_manually_created_transcript([lang, "en"])
        except Exception:
            transcript = transcript_list.find_generated_transcript([lang, "en"])

        entries = transcript.fetch()
        return [
            {
                "start": entry.start,
                "duration": entry.duration,
                "text": entry.text,
            }
            for entry in entries
        ]
    except Exception as e:
        print(f"字幕取得エラー: {e}")
        return []


def format_timestamp(seconds):
    """秒をHH:MM:SS形式に変換"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def get_transcript_chunk(transcript, start, end):
    """指定範囲のトランスクリプトを抽出"""
    return [
        entry for entry in transcript
        if entry["start"] >= start and entry["start"] < end
    ]


def transcript_to_text(transcript):
    """トランスクリプトをタイムスタンプ付きテキストに変換"""
    lines = []
    for entry in transcript:
        ts = format_timestamp(entry["start"])
        lines.append(f"[{ts}] {entry['text']}")
    return "\n".join(lines)
