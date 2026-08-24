#!/usr/bin/env bash
# =====================================================================
#  さんすうバトル！ — GitHub Pages 公開スクリプト
#
#  使い方（このフォルダの中で実行）:
#     bash github-upload.sh
#
#  必要なもの:
#     - git
#     - GitHub の Personal Access Token（下の「トークンの作り方」参照）
#
#  トークンの作り方:
#     https://github.com/settings/personal-access-tokens/new
#       Repository access : All repositories（新規作成するので）
#       Permissions       : Repository permissions
#                             Contents      → Read and write
#                             Administration→ Read and write   ← Pages有効化に必要
#                             Pages         → Read and write
#       Expiration        : 7 days くらいで十分
#     使い終わったら https://github.com/settings/tokens で失効させてください。
# =====================================================================
set -euo pipefail

USER_NAME="ganapati0330"
REPO_NAME="${REPO_NAME:-sansu-battle}"
REPO_DESC="小学1〜3年生の算数バトルゲーム（フテ猫・クロネコさん・チャッピーちゃん）"
BRANCH="main"

say()  { printf '\033[1;36m▶ %s\033[0m\n' "$*"; }
ok()   { printf '\033[1;32m✔ %s\033[0m\n' "$*"; }
die()  { printf '\033[1;31m✘ %s\033[0m\n' "$*" >&2; exit 1; }

command -v git  >/dev/null || die "git が見つかりません。"
command -v curl >/dev/null || die "curl が見つかりません。"
[ -f index.html ] || die "index.html が見つかりません。このスクリプトは公開フォルダの中で実行してください。"

# ---- トークン入力（画面に表示されません） ----
if [ -z "${GITHUB_TOKEN:-}" ]; then
  printf 'GitHub Personal Access Token を貼り付けてEnter（入力は表示されません）: '
  stty -echo; read -r GITHUB_TOKEN; stty echo; printf '\n'
fi
[ -n "${GITHUB_TOKEN}" ] || die "トークンが空です。"

API="https://api.github.com"
AUTH=(-H "Authorization: Bearer ${GITHUB_TOKEN}"
      -H "Accept: application/vnd.github+json"
      -H "X-GitHub-Api-Version: 2022-11-28")

# ---- 認証チェック ----
say "トークンを確認しています…"
USER_JSON=$(curl -sS "${AUTH[@]}" "${API}/user" || true)
LOGIN=$(printf '%s' "${USER_JSON}" | sed -n 's/.*"login"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1)
if [ -z "${LOGIN}" ]; then
  die "認証に失敗しました。トークンが正しいか、期限が切れていないか確認してください。"
fi
ok "ログイン: ${LOGIN}"

# ---- リポジトリ作成（すでにあればそのまま使う） ----
say "リポジトリ ${LOGIN}/${REPO_NAME} を用意しています…"
CODE=$(curl -s -o /dev/null -w '%{http_code}' "${AUTH[@]}" "${API}/repos/${LOGIN}/${REPO_NAME}")
if [ "${CODE}" = "404" ]; then
  curl -fsS -X POST "${AUTH[@]}" "${API}/user/repos" \
    -d "{\"name\":\"${REPO_NAME}\",\"description\":\"${REPO_DESC}\",\"private\":false,\"has_issues\":true,\"has_wiki\":false}" \
    >/dev/null
  ok "新しく作成しました。"
elif [ "${CODE}" = "200" ]; then
  ok "すでにあるリポジトリを使います。"
else
  die "リポジトリの確認に失敗しました（HTTP ${CODE}）。"
fi

# ---- push ----
say "ファイルをアップロードしています…"
if [ ! -d .git ]; then
  git init -q
  git checkout -q -b "${BRANCH}" 2>/dev/null || git branch -M "${BRANCH}"
fi
git -c user.name="${LOGIN}" -c user.email="${LOGIN}@users.noreply.github.com" add -A
if git diff --cached --quiet 2>/dev/null; then
  say "変更はありませんでした。"
else
  git -c user.name="${LOGIN}" -c user.email="${LOGIN}@users.noreply.github.com" \
      commit -q -m "さんすうバトル！ を公開/更新"
fi
git remote remove origin 2>/dev/null || true
git remote add origin "https://x-access-token:${GITHUB_TOKEN}@github.com/${LOGIN}/${REPO_NAME}.git"
git push -q -u origin "${BRANCH}" --force
# トークンが .git/config に残らないように書き換える
git remote set-url origin "https://github.com/${LOGIN}/${REPO_NAME}.git"
ok "アップロード完了。"

# ---- GitHub Pages を有効化 ----
say "GitHub Pages を有効にしています…"
PCODE=$(curl -s -o /dev/null -w '%{http_code}' -X POST "${AUTH[@]}" \
  "${API}/repos/${LOGIN}/${REPO_NAME}/pages" \
  -d "{\"source\":{\"branch\":\"${BRANCH}\",\"path\":\"/\"}}")
if [ "${PCODE}" = "201" ]; then
  ok "Pages を有効にしました。"
elif [ "${PCODE}" = "409" ]; then
  ok "Pages はすでに有効です。"
else
  printf '\033[1;33m! Pages の自動設定ができませんでした（HTTP %s）。\n' "${PCODE}"
  printf '  リポジトリの Settings → Pages で Branch に「%s / (root)」を選んで Save してください。\033[0m\n' "${BRANCH}"
fi

echo
ok "公開URL:  https://${LOGIN}.github.io/${REPO_NAME}/"
echo   "         （反映まで1〜2分かかることがあります）"
echo
printf '\033[1;33m※ 使い終わったトークンは https://github.com/settings/tokens で失効させてください。\033[0m\n'
