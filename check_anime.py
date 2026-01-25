import json
import os
import requests
import time
from datetime import datetime, timezone

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
ANNICT_TOKEN = os.environ.get("ANNICT_TOKEN")

ANNICT_API = "https://api.annict.com/graphql"

def load_works():
    with open("works.json", "r", encoding="utf-8") as f:
        return json.load(f)

def save_works(works):
    with open("works.json", "w", encoding="utf-8") as f:
        json.dump(works, f, ensure_ascii=False, indent=2)

def send_discord_embed(title, description, url, image_url):
    payload = {
        "embeds": [
            {
                "title": title,
                "description": description,
                "url": url,
                "image": {
                    "url": image_url
                }
            }
        ]
    }
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=payload)
    except Exception as e:
        print(f"Error sending Discord webhook: {e}")

def get_latest_episode(work_id):
    # ▼▼▼ 修正: last: 1 を last: 5 に変更（数話分まとめて取得する） ▼▼▼
    query = """
    query ($annictIds: [Int!]) {
      searchWorks(annictIds: $annictIds) {
        nodes {
          title
          episodes(last: 5) {
            nodes {
              number
              title
              recordsCount
            }
          }
          image {
            facebookOgImageUrl
            recommendedImageUrl
          }
        }
      }
    }
    """

    headers = {
        "Authorization": f"Bearer {ANNICT_TOKEN}"
    }

    try:
        response = requests.post(
            ANNICT_API,
            json={"query": query, "variables": {"annictIds": [int(work_id)]}},
            headers=headers
        )
        
        if response.status_code != 200:
            print(f"API Error: Status {response.status_code}")
            return 0, "APIエラー", ""

        data = response.json()
        
        if "errors" in data:
            print(f"GraphQL Error: {data['errors']}")
            return 0, "APIエラー", ""

        if not data.get("data") or not data["data"]["searchWorks"]["nodes"]:
            print(f"Error: Work ID {work_id} not found.")
            return 0, "不明", ""

        work = data["data"]["searchWorks"]["nodes"][0]
        episodes_list = work["episodes"]["nodes"]
        
        # 画像URL取得
        image_url = ""
        if work.get("image"):
            image_url = work["image"].get("facebookOgImageUrl") or work["image"].get("recommendedImageUrl") or ""
        
        if not episodes_list:
            return 0, "エピソード未登録", image_url

        # ▼▼▼ 修正: 新しい順にチェックして、放送済みのものを探す ▼▼▼
        # Annictは古い順(昇順)で返してくることが多いので、reversedで逆順(新しい順)にする
        for episode in reversed(episodes_list):
            if episode["recordsCount"] > 0:
                # 記録がある(=放送された)エピソードが見つかったらそれを返す
                return int(episode["number"]), episode["title"], image_url
            else:
                # 記録がない場合はログを出して次(一つ前)の話をチェック
                print(f"    (Skipping Ep {episode['number']}: Pre-release data)")

        # 全部チェックしても放送済みがなければ0
        return 0, "未放送", ""

    except Exception as e:
        print(f"Exception in get_latest_episode: {e}")
        return 0, "例外発生", ""

def main():
    print("--- Start Checking ---")

    if ANNICT_TOKEN:
        print(f"Token Check: OK (Length: {len(ANNICT_TOKEN)})")
    else:
        print("Token Check: FAILED (Token is empty or None)")

    works = load_works()
    updated = False

    for work in works:
        work_id = work["work_id"]
        title = work["title"]
        last_episode = work["last_episode"]
        streaming_url = work.get("streaming_url", "")
        
        print(f"Checking: {title} (ID: {work_id}, Last Ep: {last_episode})")

        latest_episode, episode_title, image_url = get_latest_episode(work_id)
        
        if latest_episode == 0:
             print(f"  -> No aired episode found yet.")
             time.sleep(2)
             continue

        print(f"  -> Latest Aired Ep: {latest_episode}, Title: {episode_title}")

        if latest_episode > last_episode:
            print("  -> New episode found! Sending notification...")
            
            embed_title = f"キョン！{title}の最新話が更新されたわよ！"
            embed_description = f"第 {latest_episode} 話「{episode_title}」よ！"
        
            send_discord_embed(
                embed_title,
                embed_description,
                streaming_url,
                image_url
            )
            print("  -> Notification sent.")
            
            work["last_episode"] = latest_episode
            updated = True
        else:
            print("  -> No update.")
        
        time.sleep(2)

    if updated:
        save_works(works)
        print("--- Works updated ---")
    else:
        print("--- No changes ---")

if __name__ == "__main__":
    main()
