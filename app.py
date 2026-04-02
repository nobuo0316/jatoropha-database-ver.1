import io
from typing import Any, Dict, List

import pandas as pd
import streamlit as st
from postgrest.exceptions import APIError
from supabase import Client, create_client


# =========================================================
# Page
# =========================================================
APP_TITLE = st.secrets.get("APP_TITLE", "Jatropha Knowledge DB")
st.set_page_config(page_title=APP_TITLE, page_icon="🌱", layout="wide")


# =========================================================
# Supabase
# =========================================================
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# =========================================================
# Session state
# =========================================================
if "user" not in st.session_state:
    st.session_state.user = None


# =========================================================
# Helpers
# =========================================================
def get_text_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    if isinstance(value, str):
        return [x.strip() for x in value.split(",") if x.strip()]
    return []


def normalize_int(value: Any, default=None):
    try:
        if value is None or value == "":
            return default
        return int(value)
    except Exception:
        return default


def badge_reliability(value: str) -> str:
    if value == "high":
        return "🟢 high"
    if value == "medium":
        return "🟡 medium"
    if value == "low":
        return "🔴 low"
    return value or "-"


def require_login():
    if not st.session_state.user:
        st.stop()


def is_admin() -> bool:
    user = st.session_state.user or {}
    return user.get("role") == "admin"


def dataframe_download(df: pd.DataFrame, filename: str, label: str):
    csv_bytes = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label=label,
        data=csv_bytes,
        file_name=filename,
        mime="text/csv"
    )


# =========================================================
# Auth
# =========================================================
def login_form():
    st.title(APP_TITLE)
    st.caption("Jatropha専用ログイン")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login", type="primary"):
        if not username.strip() or not password:
            st.error("username と password を入力してください。")
            return

        try:
            res = supabase.rpc(
                "jatropha_app_login",
                {
                    "p_username": username.strip(),
                    "p_password": password,
                }
            ).execute()

            rows = res.data or []
            if rows and rows[0]["ok"]:
                st.session_state.user = rows[0]
                st.success("ログイン成功")
                st.rerun()

            elif rows:
                row = rows[0]
                lock_info = row.get("locked_until")
                fa = row.get("failed_attempts", 0)
                if lock_info:
                    st.error(f"ログイン失敗。ロック中です。locked_until: {lock_info}")
                else:
                    st.error(f"ログイン失敗。failed_attempts: {fa}/5")
            else:
                st.error("ログイン失敗。レスポンスが空です。")

        except APIError as e:
            st.error("Supabase RPC error")
            st.code(str(e))
        except Exception as e:
            st.error("Unexpected error")
            st.code(repr(e))


def logout():
    st.session_state.user = None
    st.rerun()


# =========================================================
# Data access
# =========================================================
def fetch_theme_master() -> List[Dict[str, Any]]:
    res = (
        supabase.table("jatropha_theme_master")
        .select("*")
        .eq("is_active", True)
        .order("sort_order")
        .execute()
    )
    return res.data or []


def fetch_papers(active_only: bool = False) -> List[Dict[str, Any]]:
    query = supabase.table("jatropha_papers").select("*").order("publication_year", desc=True)
    if active_only:
        query = query.eq("is_active", True)
    res = query.execute()
    return res.data or []


def fetch_cards() -> List[Dict[str, Any]]:
    res = (
        supabase.table("jatropha_v_knowledge_cards")
        .select("*")
        .order("importance", desc=True)
        .execute()
    )
    return res.data or []


def insert_paper(payload: Dict[str, Any]):
    return supabase.table("jatropha_papers").insert(payload).execute()


def update_paper(paper_id: str, payload: Dict[str, Any]):
    return supabase.table("jatropha_papers").update(payload).eq("id", paper_id).execute()


def insert_card(payload: Dict[str, Any]):
    return supabase.table("jatropha_knowledge_cards").insert(payload).execute()


def update_card(card_id: str, payload: Dict[str, Any]):
    return supabase.table("jatropha_knowledge_cards").update(payload).eq("id", card_id).execute()


def fetch_user_debug():
    res = supabase.table("jatropha_v_app_user_debug").select("*").order("id").execute()
    return res.data or []


# =========================================================
# Render helpers
# =========================================================
def render_card(c: Dict[str, Any]):
    with st.container(border=True):
        col1, col2 = st.columns([4, 1])
        with col1:
            st.subheader(c.get("card_title", "-"))
            st.caption(
                f"テーマ: {c.get('theme', '-')}"
                + (f" / サブテーマ: {c.get('subtheme')}" if c.get("subtheme") else "")
            )
        with col2:
            st.markdown(f"**重要度:** {c.get('importance', '-')}")
            st.markdown(f"**信頼度:** {badge_reliability(c.get('reliability'))}")

        st.markdown("**わかりやすい説明**")
        st.write(c.get("simple_explanation") or "-")

        if c.get("detailed_explanation"):
            with st.expander("詳しい説明"):
                st.write(c.get("detailed_explanation"))

        if c.get("caution"):
            st.markdown("**注意点**")
            st.warning(c.get("caution"))

        tags = get_text_list(c.get("tags"))
        if tags:
            st.markdown("**タグ**")
            st.write(" / ".join(tags))

        st.markdown("---")
        st.markdown("**出典**")
        st.write(f"**論文タイトル:** {c.get('paper_title', '-')}")
        meta_parts = []
        if c.get("authors"):
            meta_parts.append(str(c.get("authors")))
        if c.get("publication_year"):
            meta_parts.append(str(c.get("publication_year")))
        if c.get("journal"):
            meta_parts.append(str(c.get("journal")))
        if meta_parts:
            st.caption(" / ".join(meta_parts))
        if c.get("url"):
            st.markdown(f"[元リンクを開く]({c['url']})")


def filter_cards(cards, theme, keyword, selected_tags, reliability):
    filtered = []
    for c in cards:
        card_tags = get_text_list(c.get("tags"))
        text_blob = " ".join([
            str(c.get("card_title", "")),
            str(c.get("simple_explanation", "")),
            str(c.get("detailed_explanation", "")),
            str(c.get("caution", "")),
            str(c.get("paper_title", "")),
            str(c.get("authors", "")),
            str(c.get("journal", "")),
            str(c.get("theme", "")),
            str(c.get("subtheme", "")),
            " ".join(card_tags),
        ]).lower()

        if theme != "すべて" and c.get("theme") != theme:
            continue
        if reliability != "すべて" and c.get("reliability") != reliability:
            continue
        if keyword and keyword.lower() not in text_blob:
            continue
        if selected_tags and not set(selected_tags).issubset(set(card_tags)):
            continue
        filtered.append(c)
    return filtered


# =========================================================
# CSV import helpers
# =========================================================
def import_papers_csv(df: pd.DataFrame):
    required = ["title", "url"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"papers CSV に必須列がありません: {missing}")

    imported = 0
    updated = 0

    for _, row in df.iterrows():
        title = str(row.get("title", "")).strip()
        url = str(row.get("url", "")).strip()

        if not title or not url:
            continue

        payload = {
            "title": title,
            "authors": str(row.get("authors")).strip() if pd.notna(row.get("authors")) else None,
            "publication_year": normalize_int(row.get("publication_year"), None),
            "journal": str(row.get("journal")).strip() if pd.notna(row.get("journal")) else None,
            "doi": str(row.get("doi")).strip() if pd.notna(row.get("doi")) else None,
            "url": url,
            "source_type": str(row.get("source_type")).strip() if pd.notna(row.get("source_type")) else "paper",
            "beginner_summary": str(row.get("beginner_summary")).strip() if pd.notna(row.get("beginner_summary")) else None,
            "detailed_summary": str(row.get("detailed_summary")).strip() if pd.notna(row.get("detailed_summary")) else None,
            "reliability": str(row.get("reliability")).strip() if pd.notna(row.get("reliability")) else "medium",
            "notes": str(row.get("notes")).strip() if pd.notna(row.get("notes")) else None,
            "is_active": bool(row.get("is_active")) if pd.notna(row.get("is_active")) else True,
            "created_by": st.session_state.user.get("user_id"),
        }

        existing = (
            supabase.table("jatropha_papers")
            .select("id")
            .eq("url", url)
            .limit(1)
            .execute()
        ).data

        if existing:
            update_paper(existing[0]["id"], payload)
            updated += 1
        else:
            insert_paper(payload)
            imported += 1

    return imported, updated


def import_cards_csv(df: pd.DataFrame):
    required = ["paper_url", "theme", "title", "simple_explanation"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"knowledge_cards CSV に必須列がありません: {missing}")

    imported = 0
    updated = 0

    for _, row in df.iterrows():
        paper_url = str(row.get("paper_url", "")).strip()
        theme = str(row.get("theme", "")).strip()
        title = str(row.get("title", "")).strip()
        simple_explanation = str(row.get("simple_explanation", "")).strip()

        if not paper_url or not theme or not title or not simple_explanation:
            continue

        paper_rows = (
            supabase.table("jatropha_papers")
            .select("id")
            .eq("url", paper_url)
            .limit(1)
            .execute()
        ).data

        if not paper_rows:
            continue

        paper_id = paper_rows[0]["id"]

        payload = {
            "paper_id": paper_id,
            "theme": theme,
            "subtheme": str(row.get("subtheme")).strip() if pd.notna(row.get("subtheme")) else None,
            "title": title,
            "simple_explanation": simple_explanation,
            "detailed_explanation": str(row.get("detailed_explanation")).strip() if pd.notna(row.get("detailed_explanation")) else None,
            "caution": str(row.get("caution")).strip() if pd.notna(row.get("caution")) else None,
            "tags": get_text_list(row.get("tags")),
            "importance": normalize_int(row.get("importance"), 3),
            "is_featured": bool(row.get("is_featured")) if pd.notna(row.get("is_featured")) else False,
            "is_active": bool(row.get("is_active")) if pd.notna(row.get("is_active")) else True,
            "created_by": st.session_state.user.get("user_id"),
        }

        existing = (
            supabase.table("jatropha_knowledge_cards")
            .select("id")
            .eq("paper_id", paper_id)
            .eq("title", title)
            .limit(1)
            .execute()
        ).data

        if existing:
            update_card(existing[0]["id"], payload)
            updated += 1
        else:
            insert_card(payload)
            imported += 1

    return imported, updated


# =========================================================
# UI
# =========================================================
if not st.session_state.user:
    login_form()
    st.stop()

user = st.session_state.user

with st.sidebar:
    st.markdown(f"**User:** {user.get('display_name') or user.get('username')}")
    st.markdown(f"**Role:** {user.get('role')}")
    if st.button("Logout"):
        logout()

    menu_options = [
        "ホーム",
        "知見カード一覧",
        "論文一覧",
    ]

    if is_admin():
        menu_options.extend([
            "管理者：論文登録",
            "管理者：論文編集",
            "管理者：知見カード登録",
            "管理者：知見カード編集",
            "管理者：CSV一括取込",
            "管理者：ユーザー確認",
        ])

    menu = st.radio("メニュー", menu_options)

theme_master = fetch_theme_master()
theme_options = ["すべて"] + [x["theme"] for x in theme_master]
cards = fetch_cards()
papers = fetch_papers(active_only=False)

st.title(APP_TITLE)
st.caption("既存アプリに触れない完全分離版")

if menu == "ホーム":
    st.markdown("## このDBの目的")
    st.write(
        """
        このアプリは、ジャトロファに関する論文・記事の内容を
        初心者でもわかりやすい形で整理して管理するためのDBです。
        """
    )

    col1, col2, col3 = st.columns(3)
    col1.metric("論文数", len([p for p in papers if p.get("is_active", True)]))
    col2.metric("知見カード数", len(cards))
    col3.metric("テーマ数", len(theme_master))

    featured = [c for c in cards if c.get("is_featured") and c.get("card_is_active", True)]
    st.markdown("## 注目カード")
    if featured:
        for c in featured[:5]:
            render_card(c)
    else:
        st.info("注目カードはまだありません。")

elif menu == "知見カード一覧":
    st.markdown("## 知見カード一覧")

    all_tags = sorted(list({tag for c in cards for tag in get_text_list(c.get("tags"))}))

    col1, col2, col3, col4 = st.columns([2, 3, 3, 2])
    with col1:
        selected_theme = st.selectbox("テーマ", theme_options, index=0)
    with col2:
        keyword = st.text_input("キーワード検索")
    with col3:
        selected_tags = st.multiselect("タグ", all_tags)
    with col4:
        reliability = st.selectbox("信頼度", ["すべて", "high", "medium", "low"], index=0)

    filtered = filter_cards(cards, selected_theme, keyword, selected_tags, reliability)
    st.caption(f"該当件数: {len(filtered)} 件")

    if filtered:
        dataframe_download(pd.DataFrame(filtered), "jatropha_knowledge_cards.csv", "CSVダウンロード")
        for c in filtered:
            render_card(c)
    else:
        st.warning("該当する知見カードがありません。")

elif menu == "論文一覧":
    st.markdown("## 論文一覧")

    active_only = st.checkbox("有効な論文のみ表示", value=True)
    paper_list = [p for p in papers if (p.get("is_active", True) if active_only else True)]
    keyword = st.text_input("タイトル・著者・掲載誌で検索")

    filtered = []
    for p in paper_list:
        blob = " ".join([
            str(p.get("title", "")),
            str(p.get("authors", "")),
            str(p.get("journal", "")),
            str(p.get("beginner_summary", "")),
            str(p.get("detailed_summary", "")),
            str(p.get("notes", "")),
        ]).lower()

        if keyword and keyword.lower() not in blob:
            continue
        filtered.append(p)

    st.caption(f"該当件数: {len(filtered)} 件")

    if filtered:
        dataframe_download(pd.DataFrame(filtered), "jatropha_papers.csv", "CSVダウンロード")

        for p in filtered:
            with st.container(border=True):
                st.subheader(p.get("title", "-"))
                st.caption(
                    " / ".join([x for x in [
                        str(p.get("authors")) if p.get("authors") else "",
                        str(p.get("publication_year")) if p.get("publication_year") else "",
                        str(p.get("journal")) if p.get("journal") else "",
                    ] if x])
                )
                c1, c2, c3 = st.columns(3)
                c1.markdown(f"**種別:** {p.get('source_type', '-')}")
                c2.markdown(f"**信頼度:** {badge_reliability(p.get('reliability'))}")
                c3.markdown(f"**有効:** {'Yes' if p.get('is_active', True) else 'No'}")

                if p.get("doi"):
                    st.write(f"**DOI:** {p.get('doi')}")
                if p.get("url"):
                    st.markdown(f"[リンクを開く]({p['url']})")
                if p.get("beginner_summary"):
                    st.markdown("**初心者向け要約**")
                    st.write(p.get("beginner_summary"))
                if p.get("detailed_summary"):
                    with st.expander("詳細要約"):
                        st.write(p.get("detailed_summary"))
                if p.get("notes"):
                    with st.expander("メモ"):
                        st.write(p.get("notes"))
    else:
        st.warning("該当する論文がありません。")

elif menu == "管理者：論文登録":
    if not is_admin():
        st.error("admin only")
        st.stop()

    st.markdown("## 管理者：論文登録")
    with st.form("paper_form"):
        title = st.text_input("論文タイトル *")
        authors = st.text_input("著者")
        publication_year = st.text_input("発行年")
        journal = st.text_input("掲載誌")
        doi = st.text_input("DOI")
        url = st.text_input("リンク(URL) *")
        source_type = st.selectbox("種別", ["paper", "report", "website", "book", "other"], index=0)
        reliability = st.selectbox("信頼度", ["high", "medium", "low"], index=1)
        beginner_summary = st.text_area("初心者向け要約", height=120)
        detailed_summary = st.text_area("詳細要約", height=180)
        notes = st.text_area("メモ", height=120)
        is_active = st.checkbox("有効", value=True)
        submitted = st.form_submit_button("論文を登録")

    if submitted:
        if not title.strip():
            st.error("論文タイトルは必須です。")
        elif not url.strip():
            st.error("リンク(URL)は必須です。")
        else:
            payload = {
                "title": title.strip(),
                "authors": authors.strip() if authors else None,
                "publication_year": normalize_int(publication_year, None),
                "journal": journal.strip() if journal else None,
                "doi": doi.strip() if doi else None,
                "url": url.strip(),
                "source_type": source_type,
                "beginner_summary": beginner_summary.strip() if beginner_summary else None,
                "detailed_summary": detailed_summary.strip() if detailed_summary else None,
                "reliability": reliability,
                "notes": notes.strip() if notes else None,
                "is_active": is_active,
                "created_by": user.get("user_id"),
            }
            try:
                insert_paper(payload)
                st.success("論文を登録しました。")
                st.rerun()
            except Exception as e:
                st.error(f"登録エラー: {e}")

elif menu == "管理者：論文編集":
    if not is_admin():
        st.error("admin only")
        st.stop()

    st.markdown("## 管理者：論文編集")
    current_papers = fetch_papers(active_only=False)
    if not current_papers:
        st.info("論文データがありません。")
        st.stop()

    label_map = {
        f"{p['title']} | {p.get('publication_year') or '-'} | {p['id']}": p
        for p in current_papers
    }
    selected_label = st.selectbox("編集する論文", list(label_map.keys()))
    p = label_map[selected_label]

    with st.form("paper_edit_form"):
        title = st.text_input("論文タイトル *", value=p.get("title", ""))
        authors = st.text_input("著者", value=p.get("authors") or "")
        publication_year = st.text_input("発行年", value="" if p.get("publication_year") is None else str(p.get("publication_year")))
        journal = st.text_input("掲載誌", value=p.get("journal") or "")
        doi = st.text_input("DOI", value=p.get("doi") or "")
        url = st.text_input("リンク(URL) *", value=p.get("url") or "")
        source_type = st.selectbox(
            "種別",
            ["paper", "report", "website", "book", "other"],
            index=["paper", "report", "website", "book", "other"].index(p.get("source_type", "paper"))
            if p.get("source_type", "paper") in ["paper", "report", "website", "book", "other"] else 0
        )
        reliability = st.selectbox(
            "信頼度",
            ["high", "medium", "low"],
            index=["high", "medium", "low"].index(p.get("reliability", "medium"))
            if p.get("reliability", "medium") in ["high", "medium", "low"] else 1
        )
        beginner_summary = st.text_area("初心者向け要約", value=p.get("beginner_summary") or "", height=120)
        detailed_summary = st.text_area("詳細要約", value=p.get("detailed_summary") or "", height=180)
        notes = st.text_area("メモ", value=p.get("notes") or "", height=120)
        is_active = st.checkbox("有効", value=p.get("is_active", True))
        submitted = st.form_submit_button("論文を更新")

    if submitted:
        payload = {
            "title": title.strip(),
            "authors": authors.strip() if authors else None,
            "publication_year": normalize_int(publication_year, None),
            "journal": journal.strip() if journal else None,
            "doi": doi.strip() if doi else None,
            "url": url.strip(),
            "source_type": source_type,
            "beginner_summary": beginner_summary.strip() if beginner_summary else None,
            "detailed_summary": detailed_summary.strip() if detailed_summary else None,
            "reliability": reliability,
            "notes": notes.strip() if notes else None,
            "is_active": is_active,
        }
        try:
            update_paper(p["id"], payload)
            st.success("論文を更新しました。")
            st.rerun()
        except Exception as e:
            st.error(f"更新エラー: {e}")

elif menu == "管理者：知見カード登録":
    if not is_admin():
        st.error("admin only")
        st.stop()

    st.markdown("## 管理者：知見カード登録")
    current_papers = fetch_papers(active_only=True)
    if not current_papers:
        st.warning("先に論文を登録してください。")
        st.stop()

    paper_map = {f"{p['title']} ({p.get('publication_year') or '-'})": p["id"] for p in current_papers}
    theme_values = [x["theme"] for x in theme_master] if theme_master else ["栽培"]

    with st.form("card_form"):
        selected_paper_label = st.selectbox("紐づける論文 *", list(paper_map.keys()))
        theme = st.selectbox("テーマ *", theme_values)
        subtheme = st.text_input("サブテーマ")
        card_title = st.text_input("カードタイトル *")
        simple_explanation = st.text_area("わかりやすい説明 *", height=140)
        detailed_explanation = st.text_area("詳しい説明", height=180)
        caution = st.text_area("注意点", height=100)
        tags_text = st.text_input("タグ（カンマ区切り）")
        importance = st.slider("重要度", min_value=1, max_value=5, value=3)
        is_featured = st.checkbox("注目カードにする", value=False)
        is_active = st.checkbox("有効", value=True)
        submitted = st.form_submit_button("知見カードを登録")

    if submitted:
        if not card_title.strip():
            st.error("カードタイトルは必須です。")
        elif not simple_explanation.strip():
            st.error("わかりやすい説明は必須です。")
        else:
            payload = {
                "paper_id": paper_map[selected_paper_label],
                "theme": theme,
                "subtheme": subtheme.strip() if subtheme else None,
                "title": card_title.strip(),
                "simple_explanation": simple_explanation.strip(),
                "detailed_explanation": detailed_explanation.strip() if detailed_explanation else None,
                "caution": caution.strip() if caution else None,
                "tags": get_text_list(tags_text),
                "importance": importance,
                "is_featured": is_featured,
                "is_active": is_active,
                "created_by": user.get("user_id"),
            }
            try:
                insert_card(payload)
                st.success("知見カードを登録しました。")
                st.rerun()
            except Exception as e:
                st.error(f"登録エラー: {e}")

elif menu == "管理者：知見カード編集":
    if not is_admin():
        st.error("admin only")
        st.stop()

    st.markdown("## 管理者：知見カード編集")

    rows = (
        supabase.table("jatropha_knowledge_cards")
        .select("*")
        .order("created_at", desc=True)
        .execute()
    ).data or []

    if not rows:
        st.info("知見カードがありません。")
        st.stop()

    label_map = {f"{r['title']} | {r['theme']} | {r['id']}": r for r in rows}
    selected_label = st.selectbox("編集する知見カード", list(label_map.keys()))
    c = label_map[selected_label]
    theme_values = [x["theme"] for x in theme_master] if theme_master else ["栽培"]

    with st.form("card_edit_form"):
        theme = st.selectbox(
            "テーマ *",
            theme_values,
            index=theme_values.index(c.get("theme")) if c.get("theme") in theme_values else 0
        )
        subtheme = st.text_input("サブテーマ", value=c.get("subtheme") or "")
        card_title = st.text_input("カードタイトル *", value=c.get("title") or "")
        simple_explanation = st.text_area("わかりやすい説明 *", value=c.get("simple_explanation") or "", height=140)
        detailed_explanation = st.text_area("詳しい説明", value=c.get("detailed_explanation") or "", height=180)
        caution = st.text_area("注意点", value=c.get("caution") or "", height=100)
        tags_text = st.text_input("タグ（カンマ区切り）", value=", ".join(get_text_list(c.get("tags"))))
        importance = st.slider("重要度", min_value=1, max_value=5, value=int(c.get("importance") or 3))
        is_featured = st.checkbox("注目カードにする", value=c.get("is_featured", False))
        is_active = st.checkbox("有効", value=c.get("is_active", True))
        submitted = st.form_submit_button("知見カードを更新")

    if submitted:
        payload = {
            "theme": theme,
            "subtheme": subtheme.strip() if subtheme else None,
            "title": card_title.strip(),
            "simple_explanation": simple_explanation.strip(),
            "detailed_explanation": detailed_explanation.strip() if detailed_explanation else None,
            "caution": caution.strip() if caution else None,
            "tags": get_text_list(tags_text),
            "importance": importance,
            "is_featured": is_featured,
            "is_active": is_active,
        }
        try:
            update_card(c["id"], payload)
            st.success("知見カードを更新しました。")
            st.rerun()
        except Exception as e:
            st.error(f"更新エラー: {e}")

elif menu == "管理者：CSV一括取込":
    if not is_admin():
        st.error("admin only")
        st.stop()

    st.markdown("## 管理者：CSV一括取込")

    tab1, tab2, tab3 = st.tabs(["papers CSV", "knowledge_cards CSV", "サンプルDL"])

    with tab1:
        st.markdown("### papers CSV を取り込む")
        uploaded = st.file_uploader("papers CSV", type=["csv"], key="papers_csv")
        if uploaded is not None:
            df = pd.read_csv(uploaded)
            st.dataframe(df, use_container_width=True)
            if st.button("papers CSV を取込", key="import_papers_btn"):
                try:
                    imported, updated = import_papers_csv(df)
                    st.success(f"papers 取込完了 imported={imported}, updated={updated}")
                    st.rerun()
                except Exception as e:
                    st.error(f"CSV取込エラー: {e}")

    with tab2:
        st.markdown("### knowledge_cards CSV を取り込む")
        uploaded = st.file_uploader("knowledge_cards CSV", type=["csv"], key="cards_csv")
        if uploaded is not None:
            df = pd.read_csv(uploaded)
            st.dataframe(df, use_container_width=True)
            if st.button("knowledge_cards CSV を取込", key="import_cards_btn"):
                try:
                    imported, updated = import_cards_csv(df)
                    st.success(f"knowledge_cards 取込完了 imported={imported}, updated={updated}")
                    st.rerun()
                except Exception as e:
                    st.error(f"CSV取込エラー: {e}")

    with tab3:
        papers_sample = pd.DataFrame([
            {
                "title": "Sample Jatropha Paper",
                "authors": "Author A; Author B",
                "publication_year": 2024,
                "journal": "Sample Journal",
                "doi": "10.0000/sample-doi",
                "url": "https://example.com/jatropha-paper-2",
                "source_type": "paper",
                "beginner_summary": "初心者向け要約",
                "detailed_summary": "詳細要約",
                "reliability": "medium",
                "notes": "メモ",
                "is_active": True,
            }
        ])
        cards_sample = pd.DataFrame([
            {
                "paper_url": "https://example.com/jatropha-paper-2",
                "theme": "栽培",
                "subtheme": "基本特性",
                "title": "ジャトロファはどんな植物か",
                "simple_explanation": "初心者向け説明",
                "detailed_explanation": "詳しい説明",
                "caution": "注意点",
                "tags": "栽培, 初心者向け, 基本",
                "importance": 5,
                "is_featured": True,
                "is_active": True,
            }
        ])

        st.markdown("### papers CSV サンプル")
        st.dataframe(papers_sample, use_container_width=True)
        dataframe_download(papers_sample, "jatropha_papers_sample.csv", "papers CSVサンプルDL")

        st.markdown("### knowledge_cards CSV サンプル")
        st.dataframe(cards_sample, use_container_width=True)
        dataframe_download(cards_sample, "jatropha_knowledge_cards_sample.csv", "knowledge_cards CSVサンプルDL")

elif menu == "管理者：ユーザー確認":
    if not is_admin():
        st.error("admin only")
        st.stop()

    st.markdown("## 管理者：ユーザー確認")
    try:
        df = pd.DataFrame(fetch_user_debug())
        if df.empty:
            st.info("ユーザーデータがありません。")
        else:
            st.dataframe(df, use_container_width=True)
    except Exception as e:
        st.error(f"表示エラー: {e}")
