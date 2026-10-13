#!/usr/bin/env python3
"""
scripts/update_stats.py

Fetches live competitive programming stats for:
- Codeforces (user: sinhakiran8723)
- LeetCode (user: KiranSinha)
- CodeChef (user: bamun_sowgo)

Regenerates assets/competitive.svg with animated numbers and graceful fallback.
"""

import os
import sys
import json
import re
import urllib.request
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(SCRIPT_DIR)
CACHE_FILE = os.path.join(SCRIPT_DIR, "stats_cache.json")
SVG_FILE = os.path.join(REPO_DIR, "assets", "competitive.svg")

# Default / Fallback stats if fresh fetch fails and no cache exists
DEFAULT_STATS = {
    "codeforces": {
        "handle": "sinhakiran8723",
        "rating": 876,
        "maxRating": 887,
        "rank": "Newbie",
        "contests": 5
    },
    "leetcode": {
        "handle": "KiranSinha",
        "total": 172,
        "easy": 131,
        "medium": 38,
        "hard": 3,
        "ranking": "1,022,653"
    },
    "codechef": {
        "handle": "bamun_sowgo",
        "rating": "1149",
        "highest": "1157",
        "stars": "1★",
        "global_rank": "101,549",
        "country_rank": "97,869"
    }
}

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[WARN] Failed to read cache: {e}")
    return DEFAULT_STATS.copy()

def save_cache(stats):
    try:
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2)
    except Exception as e:
        print(f"[WARN] Failed to write cache: {e}")

def fetch_codeforces(handle="sinhakiran8723"):
    info_url = f"https://codeforces.com/api/user.info?handles={handle}"
    rating_url = f"https://codeforces.com/api/user.rating?handle={handle}"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    req1 = urllib.request.Request(info_url, headers=headers)
    with urllib.request.urlopen(req1, timeout=12) as resp:
        data = json.loads(resp.read().decode())
        if data.get("status") != "OK":
            raise ValueError(f"Codeforces API error: {data.get('comment')}")
        user_info = data["result"][0]

    contests_count = 0
    try:
        req2 = urllib.request.Request(rating_url, headers=headers)
        with urllib.request.urlopen(req2, timeout=10) as resp2:
            r_data = json.loads(resp2.read().decode())
            if r_data.get("status") == "OK":
                contests_count = len(r_data.get("result", []))
    except Exception as e:
        print(f"[WARN] Failed to fetch CF contests list: {e}")

    return {
        "handle": handle,
        "rating": user_info.get("rating", "-"),
        "maxRating": user_info.get("maxRating", "-"),
        "rank": user_info.get("rank", "unrated").capitalize(),
        "contests": contests_count
    }

def fetch_leetcode(handle="KiranSinha"):
    query = """query getUserProfile($username: String!) {
        matchedUser(username: $username) {
            submitStats: submitStatsGlobal {
                acSubmissionNum {
                    difficulty
                    count
                }
            }
            profile {
                ranking
            }
        }
    }"""
    payload = json.dumps({"query": query, "variables": {"username": handle}})
    
    # Use curl subprocess with proper browser headers to reliably bypass Cloudflare
    cmd = [
        "curl", "-s", "-X", "POST", "https://leetcode.com/graphql",
        "-H", "content-type: application/json",
        "-H", "user-agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "-H", f"referer: https://leetcode.com/u/{handle}/",
        "--data", payload
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    if res.returncode != 0 or not res.stdout.strip():
        raise RuntimeError(f"Curl failed or empty output: {res.stderr}")
    
    data = json.loads(res.stdout)
    user = data.get("data", {}).get("matchedUser")
    if not user:
        raise ValueError("Matched user not found in LeetCode response")
    
    counts = {x["difficulty"]: x["count"] for x in user["submitStats"]["acSubmissionNum"]}
    ranking = user.get("profile", {}).get("ranking", "-")
    ranking_str = f"{ranking:,}" if isinstance(ranking, int) else str(ranking)

    return {
        "handle": handle,
        "total": counts.get("All", 0),
        "easy": counts.get("Easy", 0),
        "medium": counts.get("Medium", 0),
        "hard": counts.get("Hard", 0),
        "ranking": ranking_str
    }

def fetch_codechef(handle="bamun_sowgo"):
    url = f"https://www.codechef.com/users/{handle}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        html = resp.read().decode("utf-8", errors="ignore")

    rating_match = re.search(r'<div class="rating-number"[^>]*>\s*([0-9]+)\s*</div>', html)
    rating = rating_match.group(1) if rating_match else "-"

    highest_match = re.search(r'\(Highest Rating\s*([0-9]+)\)', html)
    highest = highest_match.group(1) if highest_match else "-"

    stars_match = re.search(r'<div class="rating-star"[^>]*>(.*?)</div>', html, re.DOTALL)
    stars = "1★"
    if stars_match:
        star_count = stars_match.group(1).count("&#9733;") or stars_match.group(1).count("★")
        stars = f"{star_count}★" if star_count > 0 else "1★"

    global_rank = "-"
    country_rank = "-"
    ranks_block = re.search(r'<div class="rating-ranks">([\s\S]*?)</div>', html)
    if ranks_block:
        g = re.search(r'<a href="/ratings/all">[\s\S]*?<strong>\s*([0-9]+)\s*</strong>', ranks_block.group(1))
        if g:
            global_rank = f"{int(g.group(1)):,}"
        c = re.search(r'filterBy=Country[^\"]*\">[\s\S]*?<strong>\s*([0-9]+)\s*</strong>', ranks_block.group(1))
        if c:
            country_rank = f"{int(c.group(1)):,}"

    return {
        "handle": handle,
        "rating": rating,
        "highest": highest,
        "stars": stars,
        "global_rank": global_rank,
        "country_rank": country_rank
    }

def generate_svg(cf, lc, cc):
    # Calculate progress bar for LeetCode
    total_solved = lc.get("total", 0)
    easy = lc.get("easy", 0)
    med = lc.get("medium", 0)
    hard = lc.get("hard", 0)
    
    bar_width = 216
    if total_solved > 0:
        w_easy = max(2, int((easy / total_solved) * bar_width))
        w_med = max(2, int((med / total_solved) * bar_width))
        w_hard = max(2, bar_width - w_easy - w_med)
    else:
        w_easy, w_med, w_hard = 0, 0, 0

    svg_content = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 840 260" width="100%" height="260" fill="none">
  <defs>
    <!-- Background Gradient -->
    <linearGradient id="comp-card-bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#161b22" />
      <stop offset="100%" stop-color="#0d1117" />
    </linearGradient>

    <!-- Card Top Border Gradients -->
    <linearGradient id="cf-glow" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#318ce7" />
      <stop offset="50%" stop-color="#ffd43b" />
      <stop offset="100%" stop-color="#d32f2f" />
    </linearGradient>

    <linearGradient id="lc-glow" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#ffa116" />
      <stop offset="100%" stop-color="#ffc01e" />
    </linearGradient>

    <linearGradient id="cc-glow" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#a67c52" />
      <stop offset="100%" stop-color="#d2a679" />
    </linearGradient>

    <linearGradient id="card-pulse-stroke" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#30363d" />
      <stop offset="50%" stop-color="#58a6ff" stop-opacity="0.5">
        <animate attributeName="stop-opacity" values="0.2;0.6;0.2" dur="4s" repeatCount="indefinite" />
      </stop>
      <stop offset="100%" stop-color="#30363d" />
    </linearGradient>
  </defs>

  <style>
    <![CDATA[
    .comp-title {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
      font-size: 15px;
      font-weight: 700;
      fill: #ffffff;
    }}
    .comp-handle {{
      font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
      font-size: 11px;
      font-weight: 500;
      fill: #7d8590;
    }}
    .comp-hero-label {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      fill: #7d8590;
    }}
    .comp-stat-num {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
      font-size: 32px;
      font-weight: 800;
      fill: #58a6ff;
      animation: numberCountUp 1.2s cubic-bezier(0.16, 1, 0.3, 1) forwards;
    }}
    .comp-badge-text {{
      font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
      font-size: 10.5px;
      font-weight: 600;
      fill: #79c0ff;
    }}
    .stat-label {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
      font-size: 11px;
      fill: #7d8590;
    }}
    .stat-val {{
      font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
      font-size: 12px;
      font-weight: 600;
      fill: #e6edf3;
    }}

    @keyframes numberCountUp {{
      0% {{
        opacity: 0;
        transform: translateY(10px);
      }}
      100% {{
        opacity: 1;
        transform: translateY(0);
      }}
    }}

    @media (prefers-reduced-motion: reduce) {{
      .comp-stat-num {{
        animation: none !important;
        opacity: 1 !important;
        transform: none !important;
      }}
    }}
    ]]>
  </style>

  <!-- ==================== CARD 1: CODEFORCES ==================== -->
  <g transform="translate(14, 14)">
    <!-- Card Frame -->
    <rect x="0" y="0" width="256" height="232" rx="12" fill="url(#comp-card-bg)" stroke="url(#card-pulse-stroke)" stroke-width="1.2" />
    <path d="M 0 12 Q 0 0 12 0 L 244 0 Q 256 0 256 12 L 256 16 L 0 16 Z" fill="url(#cf-glow)" opacity="0.85" />

    <!-- Header: Logo + Title + Handle -->
    <g transform="translate(18, 30)">
      <!-- Codeforces Bars Logo -->
      <g transform="translate(0, 1)">
        <rect x="0" y="7" width="3.5" height="9" rx="1" fill="#ffd43b" />
        <rect x="5.5" y="0" width="3.5" height="16" rx="1" fill="#318ce7" />
        <rect x="11" y="4" width="3.5" height="12" rx="1" fill="#d32f2f" />
      </g>
      <text x="24" y="14" class="comp-title">Codeforces</text>
      <text x="24" y="29" class="comp-handle">@{cf.get('handle', 'sinhakiran8723')}</text>
    </g>

    <!-- Hero Stat: Rating -->
    <g transform="translate(18, 88)">
      <text x="0" y="0" class="comp-hero-label">Current Rating</text>
      <g transform="translate(0, 30)">
        <text x="0" y="0" class="comp-stat-num" fill="#58a6ff">{cf.get('rating', '-')}</text>
      </g>
      
      <!-- Rank Badge -->
      <g transform="translate(110, 8)">
        <rect x="0" y="0" width="88" height="20" rx="10" fill="#21262d" stroke="#30363d" stroke-width="0.8" />
        <circle cx="10" cy="10" r="3.5" fill="#7d8590" />
        <text x="20" y="14" class="comp-badge-text">{cf.get('rank', 'Newbie')}</text>
      </g>
    </g>

    <!-- Divider -->
    <line x1="18" y1="148" x2="238" y2="148" stroke="#30363d" stroke-width="1" />

    <!-- Sub Stats -->
    <g transform="translate(18, 172)">
      <text x="0" y="0" class="stat-label">Max Rating</text>
      <text x="0" y="18" class="stat-val">{cf.get('maxRating', '-')}</text>

      <text x="120" y="0" class="stat-label">Contests</text>
      <text x="120" y="18" class="stat-val">{cf.get('contests', 0)}</text>
    </g>
  </g>

  <!-- ==================== CARD 2: LEETCODE ==================== -->
  <g transform="translate(292, 14)">
    <rect x="0" y="0" width="256" height="232" rx="12" fill="url(#comp-card-bg)" stroke="url(#card-pulse-stroke)" stroke-width="1.2" />
    <path d="M 0 12 Q 0 0 12 0 L 244 0 Q 256 0 256 12 L 256 16 L 0 16 Z" fill="url(#lc-glow)" opacity="0.85" />

    <!-- Header: Logo + Title + Handle -->
    <g transform="translate(18, 30)">
      <!-- LeetCode Icon -->
      <svg x="0" y="1" width="16" height="16" viewBox="0 0 24 24" fill="#ffa116">
        <path d="M13.483 0a1.374 1.374 0 0 0-.961.438L7.116 6.226l-3.854 4.126a5.266 5.266 0 0 0-1.209 2.104 5.35 5.35 0 0 0-.125.513 5.527 5.527 0 0 0 .062 2.362 5.874 5.874 0 0 0 .749 1.877l3.125 4.546a1.377 1.377 0 0 0 1.134.616h9.191a1.375 1.375 0 0 0 1.375-1.375v-1.167a1.375 1.375 0 0 0-1.375-1.375H8.718l-1.921-2.793a2.766 2.766 0 0 1-.354-.887 2.607 2.607 0 0 1-.03-.993 2.502 2.502 0 0 1 .573-.997l3.659-3.918 3.838-4.108a1.374 1.374 0 0 0-.999-2.353z"/>
      </svg>
      <text x="24" y="14" class="comp-title">LeetCode</text>
      <text x="24" y="29" class="comp-handle">@{lc.get('handle', 'KiranSinha')}</text>
    </g>

    <!-- Hero Stat: Solved -->
    <g transform="translate(18, 88)">
      <text x="0" y="0" class="comp-hero-label">Problems Solved</text>
      <g transform="translate(0, 30)">
        <text x="0" y="0" class="comp-stat-num" fill="#ffa116">{total_solved}</text>
      </g>
      
      <!-- Ranking Badge -->
      <g transform="translate(100, 8)">
        <rect x="0" y="0" width="118" height="20" rx="10" fill="#21262d" stroke="#30363d" stroke-width="0.8" />
        <text x="59" y="14" text-anchor="middle" class="comp-badge-text">Rank #{lc.get('ranking', '-')}</text>
      </g>
    </g>

    <!-- Solved Distribution Progress Bar -->
    <g transform="translate(18, 142)">
      <rect x="0" y="0" width="{bar_width}" height="5" rx="2.5" fill="#21262d" />
      <rect x="0" y="0" width="{w_easy}" height="5" rx="2.5" fill="#00b8a3" />
      <rect x="{w_easy}" y="0" width="{w_med}" height="5" rx="2.5" fill="#ffc01e" />
      <rect x="{w_easy + w_med}" y="0" width="{w_hard}" height="5" rx="2.5" fill="#ff375f" />
    </g>

    <!-- Sub Stats: Easy / Med / Hard -->
    <g transform="translate(18, 172)">
      <text x="0" y="0" class="stat-label">Easy</text>
      <text x="0" y="18" class="stat-val" fill="#00b8a3">{easy}</text>

      <text x="75" y="0" class="stat-label">Medium</text>
      <text x="75" y="18" class="stat-val" fill="#ffc01e">{med}</text>

      <text x="150" y="0" class="stat-label">Hard</text>
      <text x="150" y="18" class="stat-val" fill="#ff375f">{hard}</text>
    </g>
  </g>

  <!-- ==================== CARD 3: CODECHEF ==================== -->
  <g transform="translate(570, 14)">
    <rect x="0" y="0" width="256" height="232" rx="12" fill="url(#comp-card-bg)" stroke="url(#card-pulse-stroke)" stroke-width="1.2" />
    <path d="M 0 12 Q 0 0 12 0 L 244 0 Q 256 0 256 12 L 256 16 L 0 16 Z" fill="url(#cc-glow)" opacity="0.85" />

    <!-- Header: Logo + Title + Handle -->
    <g transform="translate(18, 30)">
      <!-- CodeChef Star / Chef Badge -->
      <g transform="translate(0, 1)">
        <circle cx="8" cy="8" r="8" fill="#5b4638" />
        <text x="8" y="12" font-size="10" text-anchor="middle" fill="#ffffff">★</text>
      </g>
      <text x="24" y="14" class="comp-title">CodeChef</text>
      <text x="24" y="29" class="comp-handle">@{cc.get('handle', 'bamun_sowgo')}</text>
    </g>

    <!-- Hero Stat: Rating -->
    <g transform="translate(18, 88)">
      <text x="0" y="0" class="comp-hero-label">Current Rating</text>
      <g transform="translate(0, 30)">
        <text x="0" y="0" class="comp-stat-num" fill="#d2a679">{cc.get('rating', '-')}</text>
      </g>
      
      <!-- Stars / Div Badge -->
      <g transform="translate(110, 8)">
        <rect x="0" y="0" width="88" height="20" rx="10" fill="#21262d" stroke="#30363d" stroke-width="0.8" />
        <text x="44" y="14" text-anchor="middle" class="comp-badge-text">{cc.get('stars', '1★')} (Div 4)</text>
      </g>
    </g>

    <!-- Divider -->
    <line x1="18" y1="148" x2="238" y2="148" stroke="#30363d" stroke-width="1" />

    <!-- Sub Stats -->
    <g transform="translate(18, 172)">
      <text x="0" y="0" class="stat-label">Highest</text>
      <text x="0" y="18" class="stat-val">{cc.get('highest', '-')}</text>

      <text x="75" y="0" class="stat-label">Global</text>
      <text x="75" y="18" class="stat-val">#{cc.get('global_rank', '-')}</text>

      <text x="150" y="0" class="stat-label">India</text>
      <text x="150" y="18" class="stat-val">#{cc.get('country_rank', '-')}</text>
    </g>
  </g>
</svg>
"""
    return svg_content

def main():
    print("=" * 60)
    print(" Competitive Programming Stats Updater ")
    print("=" * 60)
    
    cached = load_cache()
    current_stats = {
        "codeforces": cached.get("codeforces", DEFAULT_STATS["codeforces"]),
        "leetcode": cached.get("leetcode", DEFAULT_STATS["leetcode"]),
        "codechef": cached.get("codechef", DEFAULT_STATS["codechef"])
    }

    # 1. Fetch Codeforces
    print("\n[1/3] Fetching Codeforces stats (handle: sinhakiran8723)...")
    try:
        cf_stats = fetch_codeforces("sinhakiran8723")
        current_stats["codeforces"] = cf_stats
        print(f"      ✓ Success: Rating={cf_stats['rating']}, Max={cf_stats['maxRating']}, Rank={cf_stats['rank']}, Contests={cf_stats['contests']}")
    except Exception as e:
        print(f"      ✗ Warning: Failed ({e}). Using last known stats.")
        print(f"        Fallback: {current_stats['codeforces']}")

    # 2. Fetch LeetCode
    print("\n[2/3] Fetching LeetCode stats (handle: KiranSinha)...")
    try:
        lc_stats = fetch_leetcode("KiranSinha")
        current_stats["leetcode"] = lc_stats
        print(f"      ✓ Success: Total={lc_stats['total']} (Easy={lc_stats['easy']}, Med={lc_stats['medium']}, Hard={lc_stats['hard']}), Rank={lc_stats['ranking']}")
    except Exception as e:
        print(f"      ✗ Warning: Failed ({e}). Using last known stats.")
        print(f"        Fallback: {current_stats['leetcode']}")

    # 3. Fetch CodeChef
    print("\n[3/3] Fetching CodeChef stats (handle: bamun_sowgo)...")
    try:
        cc_stats = fetch_codechef("bamun_sowgo")
        current_stats["codechef"] = cc_stats
        print(f"      ✓ Success: Rating={cc_stats['rating']}, Highest={cc_stats['highest']}, Stars={cc_stats['stars']}, Global={cc_stats['global_rank']}, Country={cc_stats['country_rank']}")
    except Exception as e:
        print(f"      ✗ Warning: Failed ({e}). Using last known stats.")
        print(f"        Fallback: {current_stats['codechef']}")

    # Save to cache
    save_cache(current_stats)

    # Generate assets/competitive.svg
    print("\n[4/4] Regenerating assets/competitive.svg...")
    os.makedirs(os.path.dirname(SVG_FILE), exist_ok=True)
    svg_code = generate_svg(
        current_stats["codeforces"],
        current_stats["leetcode"],
        current_stats["codechef"]
    )
    with open(SVG_FILE, "w", encoding="utf-8") as f:
        f.write(svg_code)
    print(f"      ✓ Wrote {SVG_FILE}")

    print("\n" + "=" * 60)
    print(" SUMMARY OF FETCHED STATS ")
    print("=" * 60)
    print(f"• Codeforces : Rating {current_stats['codeforces']['rating']} (Max {current_stats['codeforces']['maxRating']}) | {current_stats['codeforces']['rank']} | {current_stats['codeforces']['contests']} contests")
    print(f"• LeetCode   : {current_stats['leetcode']['total']} Solved (Easy {current_stats['leetcode']['easy']} | Med {current_stats['leetcode']['medium']} | Hard {current_stats['leetcode']['hard']}) | Rank #{current_stats['leetcode']['ranking']}")
    print(f"• CodeChef   : Rating {current_stats['codechef']['rating']} (Max {current_stats['codechef']['highest']}) | {current_stats['codechef']['stars']} | Global #{current_stats['codechef']['global_rank']} | India #{current_stats['codechef']['country_rank']}")
    print("=" * 60)

if __name__ == "__main__":
    main()
