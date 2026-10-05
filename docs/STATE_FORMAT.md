# .state/ のデータ形式

`.state/` 配下のファイルに、どんなデータがどの JSON 構成で入っているかをまとめます。
どの workflow がいつ書き込むかは [DATA_FLOW.md](DATA_FLOW.md) を参照してください。
GitHub 全体の★数のデータ（GitHub Releases に置く Parquet）は [RELEASE_DATA.md](RELEASE_DATA.md) を参照してください。

| ファイル | 書き込み元 | 中身 |
|---|---|---|
| [`stars.json`](#starsjson) | `scripts/ranking.py` | 掲載中のフレームワークの日ごとの★数 |
| [`rpg.json`](#rpgjson) | `scripts/rpg.py` | テキスト RPG の勇者の状態・日誌・周回の記録 |
| [`last-run`](#last-run) | update-ranking.yml の Commit state ステップ | 最終実行日 |

共通の決まり（`stars.json` についての決まり。`rpg.json` は[その節](#rpgjson)を参照）:

- 日付はすべて JST の `YYYY-MM-DD`（文字列）
- リポジトリは `owner/repo` の形の文字列で、`frameworks.json` に書いた表記（大文字小文字もそのまま）
- 記録は削除せず無制限に残す（`scripts/history.py` の `KEEP_DAYS = None`）
- インデント（2 スペース）付きの整形済み JSON（UTF-8）で保存し、キーは名前順（日付は古い順）に並べる。
  名前順は大文字小文字を区別する文字コード順（`DioxusLabs/…` が `facebook/…` より前）
- 毎日の workflow の最後に github-actions[bot] が master に直接コミットする（変更が無ければコミットしない）

---

## stars.json

掲載中のフレームワーク（`frameworks.json` の `repos`）の★数を、日付ごとに記録します。

```json
{
  "2026-10-01": {
    "DioxusLabs/dioxus": 39303,
    "QwikDev/qwik": 22064,
    "facebook/react": 250849,
    "gatsbyjs/gatsby": 55941
  },
  "2026-10-02": {
    "DioxusLabs/dioxus": 39350,
    "QwikDev/qwik": 22070,
    "facebook/react": 250901,
    "gatsbyjs/gatsby": 55945
  }
}
```

（実際には 1 日に掲載中の全リポジトリが入ります。2 日目は形を示すための例です）

| 階層 | キー | 値 |
|---|---|---|
| 1 | 日付（JST） | その日の記録（オブジェクト） |
| 2 | リポジトリ（`owner/repo`） | ★数（整数） |

- frontend / backend の区別は持たない（どのカテゴリかは `frameworks.json` で分かる）
- キーのリポジトリ名は `frameworks.json` に書いた名前（リネームされても書いた名前のまま）
- 記録しないもの:
  - 見つからない（404）・アーカイブ済み・`STALE_DAYS` 日以上 push が無いリポジトリ（ランキングから除外されたもの）
  - ★数の取得に失敗したカテゴリ（そのカテゴリのリポジトリがまるごと無い。
    その日のうちに再実行して取得できれば、そのときの値が追加される）
- 同じ日に複数回実行した場合は、リポジトリごとにその日最初に記録した値を残す（手動実行しても定期実行の値が変わらない）
- `--dry-run` / `--sample` のときは書き込まない。`--category` を指定したときは指定したカテゴリだけ記録する（workflow では使っていない）

使い方の例: ある日と 7 日前の★数の差で伸び幅を出す（`history.base_date()` が起点の日付を選ぶ）。

---

## rpg.json

テキスト RPG（[README](../README.md#勇者の冒険テキスト-rpg)）の状態です。`scripts/rpg.py` が毎日 1 日分進めて上書きします。
世界の設定（エリア・敵・アイテム）は `rpg_world.json` にあり、ここには勇者の状態だけを持ちます。

```json
{
  "day": 37,
  "lap": 1,
  "lap_day": 37,
  "pos": 26,
  "boss_cleared": ["草原"],
  "hero": {"level": 7, "exp": 120, "max_hp": 90, "hp": 74, "base_atk": 23, "base_def": 8,
           "gold": 340, "potions": 2, "weapon": {"name": "鉄の剣", "power": 7}, "armor": null},
  "kills": 41,
  "deaths": 0,
  "last_date": "2026-11-11",
  "last": {"date": "2026-11-11", "contributions": 3, "steps": 2, "events": ["ウルフを倒した！ (+10EXP)", "…"]},
  "journal": [{"date": "2026-11-11", "contributions": 3, "text": "ウルフを倒した！ (+10EXP) / …"}],
  "records": [{"lap": 1, "days": 92, "deaths": 1, "level": 12, "cleared_on": "2027-01-05"}]
}
```

| 項目 | 中身 |
|---|---|
| `day` | 通算の日数（周回をまたいで数える） |
| `lap` / `lap_day` | 何周目か / その周の何日目か |
| `pos` | 今いるマス（0 から。エリアの最初のマスが町、最後のマスがボス） |
| `boss_cleared` | この周で倒したボスのエリア名 |
| `hero` | レベル、経験値（次のレベルまでの途中の値）、HP、基本の攻撃力・防御力、所持金、回復薬、装備 |
| `kills` / `deaths` | この周で倒した敵の数 / 力尽きた回数 |
| `last_date` | 最後に進めた日（JST）。この日以前の日付では進めない（同じ日に再実行しても進まない） |
| `last` | 最後に進めた日の結果（`date` は進めた日、`contributions` はその前日のコントリビューション数、進んだ歩数、出来事） |
| `journal` | 日誌。新しい順に直近 30 日分（`JOURNAL_DAYS`） |
| `records` | クリアした周の記録（何日でクリアしたか、力尽きた回数、レベル）。無制限に残す |

- 魔王を倒すと `records` に記録を足し、`lap` を 1 増やして、`pos`・`hero`・`kills`・`deaths` を最初の状態に戻します。
- コントリビューション数を取得できなかった日は、その日から先を進めません。次の実行で `last_date` の翌日から 1 日ずつ進めます（最大 7 日分。`CATCH_UP_DAYS`）。
- 読み込むときに、足りない項目は初期値で補い、`rpg_world.json` を縮めて世界の外に出た `pos` は最後のマスに戻します。

---

## last-run

最終実行日（JST）が 1 行だけ入ったテキストファイルです（JSON ではありません）。

```
2026-10-01
```

毎日の workflow で上書きします。60 日間コミットが無いと scheduled workflow が止まるのを防ぐための keepalive 用で、
データとしての使い道はありません。

---

## 読み方の例

```python
import json

def load(name):
    try:
        with open(f".state/{name}", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

stars = load("stars.json")
if stars:
    day = max(stars)                            # 最新の日付
    top = sorted(stars[day].items(), key=lambda kv: -kv[1])[:5]
    print(day, top)
```
