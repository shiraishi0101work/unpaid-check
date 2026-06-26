import re
from googleapiclient.discovery import build
import config


def get_comments(video_id, max_results=100):
    """YouTubeコメントを取得（いいね順）"""
    if not config.YOUTUBE_API_KEY:
        return []

    try:
        youtube = build("youtube", "v3", developerKey=config.YOUTUBE_API_KEY)

        comments = []
        request = youtube.commentThreads().list(
            part="snippet",
            videoId=video_id,
            maxResults=min(max_results, 100),
            order="relevance",
            textFormat="plainText",
        )

        while request and len(comments) < max_results:
            response = request.execute()
            for item in response.get("items", []):
                snippet = item["snippet"]["topLevelComment"]["snippet"]
                text = snippet["textDisplay"]
                comments.append({
                    "text": text,
                    "likes": snippet.get("likeCount", 0),
                    "timestamp_mentions": extract_timestamps(text),
                })

            if len(comments) >= max_results:
                break
            request = youtube.commentThreads().list_next(request, response)

        return sorted(comments, key=lambda c: c["likes"], reverse=True)[:max_results]

    except Exception as e:
        print(f"コメント取得エラー: {e}")
        return []


def extract_timestamps(text):
    """テキストからタイムスタンプを抽出"""
    pattern = r'(\d{1,2}:\d{2}(?::\d{2})?)'
    return re.findall(pattern, text)


def parse_timestamp_to_seconds(ts):
    """タイムスタンプ文字列を秒に変換"""
    parts = ts.split(":")
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    elif len(parts) == 2:
        return int(parts[0]) * 60 + int(parts[1])
    return 0


def get_comment_timestamps(comments):
    """コメントからタイムスタンプ付きの注目ポイントを抽出"""
    timestamp_map = {}
    for comment in comments:
        for ts in comment["timestamp_mentions"]:
            seconds = parse_timestamp_to_seconds(ts)
            if seconds not in timestamp_map:
                timestamp_map[seconds] = {
                    "time": seconds,
                    "timestamp": ts,
                    "mentions": 0,
                    "total_likes": 0,
                    "sample_comments": [],
                }
            timestamp_map[seconds]["mentions"] += 1
            timestamp_map[seconds]["total_likes"] += comment["likes"]
            if len(timestamp_map[seconds]["sample_comments"]) < 3:
                timestamp_map[seconds]["sample_comments"].append(comment["text"][:100])

    return sorted(timestamp_map.values(), key=lambda x: x["total_likes"], reverse=True)
