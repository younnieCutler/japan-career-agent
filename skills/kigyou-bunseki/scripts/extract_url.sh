#!/usr/bin/env bash
# kigyou-bunseki: extract company/job data from a URL using the 3-tier pipeline
# Usage: ./extract_url.sh <URL>
#
# Output: key=value pairs, one per line
# Exit codes: 0 = data extracted, 1 = all tiers failed

URL="${1:?Usage: extract_url.sh <URL>}"
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# ── Tier 1: curl ──
html=$(curl -sL -A "$UA" --connect-timeout 10 --max-time 15 "$URL" 2>/dev/null || true)

if [ -n "$html" ]; then
  # Extract title
  title=$(echo "$html" | grep -o '<title>[^<]*' | sed 's/<title>//' | head -1)

  # Extract meta description
  meta_desc=$(echo "$html" | grep -oi '<meta[^>]*name="description"[^>]*content="[^"]*"' | grep -oi 'content="[^"]*"' | sed 's/content="//;s/"$//' | head -1)

  # Extract og:title
  og_title=$(echo "$html" | grep -oi '<meta[^>]*property="og:title"[^>]*content="[^"]*"' | grep -oi 'content="[^"]*"' | sed 's/content="//;s/"$//' | head -1)

  # Extract og:description
  og_desc=$(echo "$html" | grep -oi '<meta[^>]*property="og:description"[^>]*content="[^"]*"' | grep -oi 'content="[^"]*"' | sed 's/content="//;s/"$//' | head -1)

  # Check if we got meaningful data (not a 403/captcha page)
  if [ -n "$title" ] && ! echo "$title" | grep -qi "forbidden\|captcha\|error\|access denied"; then
    echo "tier=curl"
    echo "url=$URL"
    echo "title=$title"
    [ -n "$meta_desc" ] && echo "meta_description=$meta_desc"
    [ -n "$og_title" ] && echo "og_title=$og_title"
    [ -n "$og_desc" ] && echo "og_description=$og_desc"

    # Try to extract salary patterns (年収XXX万, XXX万円~XXX万円)
    salary=$(echo "$html" | grep -oE '年収[0-9,]+万?円?[~〜～][0-9,]+万円?' | head -1)
    [ -n "$salary" ] && echo "salary=$salary"

    # Extract domain for site identification
    domain=$(echo "$URL" | sed -E 's|https?://([^/]*).*|\1|')
    echo "domain=$domain"

    exit 0
  fi
fi

# ── Tier 1 failed → output domain for reference ──
domain=$(echo "$URL" | sed -E 's|https?://([^/]*).*|\1|')
echo "tier=failed_curl"
echo "url=$URL"
echo "domain=$domain"
echo "note=Tier 1 (curl) failed. Use read_url_content or search_web as fallback."
exit 1
