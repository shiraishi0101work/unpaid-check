"""
会社名正規化・ファジーマッチングユーティリティ

MFクラウド会計の取引先名（カタカナ）と
MFクラウド請求書の取引先名（漢字混じり）を突合するための変換・比較関数。

戦略:
  1. 法人格を除去（株式会社, 有限会社 等）
  2. ひらがな → カタカナ に統一
  3. 半角カタカナ → 全角カタカナ
  4. 記号・スペース除去
  5. rapidfuzz でトークンセット比率を計算
"""

import re
import jaconv

try:
    from rapidfuzz import fuzz as _fuzz
    _HAS_RAPIDFUZZ = True
except ImportError:
    _HAS_RAPIDFUZZ = False

# 除去する法人格パターン
_CORP = re.compile(
    r'株式会社|有限会社|合同会社|合資会社|合名会社|'
    r'一般社団法人|公益社団法人|一般財団法人|公益財団法人|'
    r'医療法人|社会福祉法人|学校法人|宗教法人|'
    r'カブシキガイシャ|ユウゲンガイシャ|ゴウドウガイシャ|'
    r'（株）|（有）|\(株\)|\(有\)|㈱|㈲'
)

# 除去する記号・空白
_NOISE = re.compile(r'[\s\u3000\u30FB・\-－—　]')


def normalize(name: str) -> str:
    """
    会社名を正規化して比較用文字列を返す。
    ひらがな→カタカナ、半角→全角カタカナ、法人格除去、記号除去。
    """
    if not name:
        return ""
    s = name.strip()
    s = _CORP.sub('', s)                                           # 法人格除去
    s = jaconv.h2k(s)                                              # ひらがな→カタカナ
    s = jaconv.h2z(s, kana=True, ascii=False, digit=False)        # 半角カタカナ→全角
    s = _NOISE.sub('', s)                                          # 記号・空白除去
    s = s.upper()                                                  # 英字大文字化
    return s


def similarity(name_a: str, name_b: str) -> float:
    """2つの会社名の類似度を 0.0〜1.0 で返す"""
    na, nb = normalize(name_a), normalize(name_b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    # 部分一致（一方が他方を含む）
    if na in nb or nb in na:
        shorter = min(len(na), len(nb))
        longer  = max(len(na), len(nb))
        return 0.7 + 0.3 * (shorter / longer)
    if _HAS_RAPIDFUZZ:
        return _fuzz.token_set_ratio(na, nb) / 100.0
    # フォールバック: 文字集合の Jaccard 係数
    sa, sb = set(na), set(nb)
    union = sa | sb
    return len(sa & sb) / len(union) if union else 0.0


def find_matches(
    accounting_name: str,
    billings: list[dict],
    threshold: float = 0.4,
) -> list[dict]:
    """
    会計の取引先名に対して類似した請求書を返す（スコア降順）。
    threshold: 類似度の下限（0.0〜1.0）
    """
    results = []
    for b in billings:
        score = similarity(accounting_name, b.get("取引先名", ""))
        if score >= threshold:
            results.append({**b, "_score": score})
    results.sort(key=lambda x: x["_score"], reverse=True)
    return results
