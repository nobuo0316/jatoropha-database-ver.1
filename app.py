import streamlit as st
import pandas as pd
from supabase import create_client, Client
from typing import Any, Dict, List, Optional
from datetime import datetime

st.set_page_config(page_title="Jatropha Knowledge DB", page_icon="🌱", layout="wide")

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

LOCK_MINUTES = int(st.secrets.get("LOCK_MINUTES", 15))
APP_TITLE = st.secrets.get("APP_TITLE", "Jatropha Knowledge DB")


def get_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    if isinstance(value, str):
        return [x.strip() for x in value.split(",") if x.strip()]
    return []


def to_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    try:
        if value in (None, ""):
            return default
        return int(value)
    except Exception:
        return default


def safe_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def role_label(role: str) -> str:
    return {"admin": "Admin", "viewer": "Viewer"}.get(role, role or "-")


def reliability_badge(value: str) -> str:
    return {"high": "🟢 high", "medium": "🟡 medium", "low": "🔴 low"}.get(value, value or "-")


def is_admin() -> bool:
    return st.session_state.get("user_role") == "admin"


def is_logged_in() -> bool:
    return bool(st.session_state.get("logged_in"))


def logout() -> None:
    keys = [
        "logged_in", "user_id", "username", "display_name", "user_role",
    ]
    for k in keys:
        if k in st.session_state:
            del st.session_state[k]
    st.rerun()


def rpc_login(username: str, password: str) -> Dict[str, Any]:
    res = supabase.rpc(
        "app_login",
        {
            "p_username": username,
            "p_password": password,
            "p_lock_minutes": LOCK_MINUTES,
        },
    ).execute()
    data = res.data or []
    return data[0] if data else {}


def ensure_login() -> None:
    if is_logged_in():
        return

    st.title(f"🔐 {APP_TITLE}")
    st.caption("ログインしてください")

    with st.form("login_form"):
        username = st.text_input("ユーザー名")
        password = st.text_input("パスワード", type="password")
        submitted = st.form_submit_button("ログイン", use_container_width=True)

    if submitted:
        try:
            result = rpc_login(username.strip(), password)
            if result.get("ok"):
                st.session_state["logged_in"] = True
                st.session_state["user_id"] = result.get("user_id")
                st.session_state["username"] = result.get("username")
                st.session_state["display_name"] = result.get("display_name") or result.get("username")
                st.session_state["user_role"] = result.get("role")
                st.success("ログインしました。")
                st.rerun()
            else:
                remaining = result.get("remaining_attempts")
                locked_until = result.get("locked_until")
                msg = result.get("message") or "ログインに失敗しました。"
                if locked_until:
                    st.error(f"{msg}（解除予定: {locked_until}）")
                elif remaining is not None:
                    st.error(f"{msg}（残り {remaining} 回）")
                else:
                    st.error(msg)
        except Exception as e:
            st.error(f"ログインエラー: {e}")

    st.stop()


@st.cache_data(ttl=60)
def fetch_theme_master() -> List[Dict[str, Any]]:
    res = (
        supabase.table("theme_master")
        .select("*")
        .eq("is_active", True)
        .order("sort_order")
        .execute()
    )
    return res.data or []


@st.cache_data(ttl=60)
def fetch_papers(active_only: bool = False) -> List[Dict[str, Any]]:
    query = supabase.table("papers").select("*").order("publication_year", desc=True)
    if active_only:
        query = query.eq("is_active", True)
    res = query.execute()
    return res.data or []


@st.cache_data(ttl=60)
def fetch_cards() -> List[Dict[str, Any]]:
    res = supabase.table("v_knowledge_cards").select("*").order("importance", desc=True).execute()
    return res.data or []


@st.cache_data(ttl=60)
def fetch_users() -> List[Dict[str, Any]]:
    res = (
        supabase.table("app_users")
        .select("id,username,display_name,role,is_active,failed_attempts,locked_until,created_at,updated_at")
        .order("username")
        .execute()
    )
    return res.data or []


def clear_cache() -> None:
    fetch_theme_master.clear()
    fetch_papers.clear()
    fetch_cards.clear()
    fetch_users.clear()


def insert_paper(payload: Dict[str, Any]) -> None:
    supabase.table("papers").insert(payload).execute()
    clear_cache()


def update_paper(paper_id: str, payload: Dict[str, Any]) -> None:
    supabase.table("papers").update(payload).eq("id", paper_id).execute()
    clear_cache()


def insert_card(payload: Dict[str, Any]) -> None:
    supabase.table("knowledge_cards").insert(payload).execute()
    clear_cache()


def update_card(card_id: str, payload: Dict[str, Any]) -> None:
    supabase.table("knowledge_cards").update(payload).eq("id", card_id).execute()
    clear_cache()


def create_user(username: str, display_name: str, role: str, password: str) -> Dict[str, Any]:
    res = supabase.rpc(
        "create_app_user",
        {
            "p_username": username,
            "p_display_name": display_name,
            "p_role": role,
            "p_password": password,
        },
    ).execute()
    clear_cache()
    data = res.data or []
    return data[0] if data else {}


def update_user_role(user_id: str, role: str, is_active: bool) -> None:
    supabase.table("app_users").update({"role": role, "is_active": is_active}).eq("id", user_id).execute()
    clear_cache()


def reset_user_password(user_id: str, new_password: str) -> Dict[str, Any]:
    res = supabase.rpc(
        "reset_app_user_password",
        {"p_user_id": user_id, "p_new_password": new_password},
    ).execute()
    clear_cache()
    data = res.data or []
    return data[0] if data else {}


def unlock_user(user_id: str) -> None:
    supabase.table("app_users").update({"failed_attempts": 0, "locked_until": None}).eq("id", user_id).execute()
    clear_cache()


def render_card(card: Dict[str, Any]) -> None:
    with st.container(border=True):
        c1, c2 = st.columns([4, 1])
        with c1:
            st.subheader(card.get("card_title") or "-")
            st.caption(
                f"テーマ: {card.get('theme', '-')}"
                + (f" / サブテーマ: {card.get('subtheme')}" if card.get("subtheme") else "")
            )
        with c2:
            st.markdown(f"**重要度:** {card.get('importance', '-')}")
            st.markdown(f"**信頼度:** {reliability_badge(card.get('reliability'))}")

        st.markdown("**わかりやすい説明**")
        st.write(card.get("simple_explanation") or "-")

        if card.get("detailed_explanation"):
            with st.expander("詳しい説明"):
                st.write(card.get("detailed_explanation"))

        if card.get("caution"):
            st.markdown("**注意点**")
            st.warning(card.get("caution"))

        tags = get_list(card.get("tags"))
        if tags:
            st.markdown("**タグ**")
            st.write(" / ".join(tags))

        st.markdown("---")
        st.markdown("**出典**")
        st.write(f"**論文タイトル:** {card.get('paper_title', '-')}")
        parts = [
            card.get("authors"),
            str(card.get("publication_year")) if card.get("publication_year") else None,
            card.get("journal"),
        ]
        parts = [p for p in parts if p]
        if parts:
            st.caption(" / ".join(parts))
        if card.get("url"):
            st.markdown(f"[元リンクを開く]({card['url']})")


def paper_dataframe(records: List[Dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(records)
    return df if not df.empty else pd.DataFrame(columns=[
        "id", "title", "authors", "publication_year", "journal", "doi", "url",
        "source_type", "beginner_summary", "detailed_summary", "reliability", "notes", "is_active"
    ])


def cards_dataframe(records: List[Dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(records)
    return df if not df.empty else pd.DataFrame(columns=[
        "knowledge_card_id", "paper_id", "theme", "subtheme", "card_title", "simple_explanation",
        "detailed_explanation", "caution", "tags", "importance", "is_featured", "paper_title"
    ])


def users_dataframe(records: List[Dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(records)
    return df if not df.empty else pd.DataFrame(columns=[
        "id", "username", "display_name", "role", "is_active", "failed_attempts", "locked_until"
    ])


def download_csv(df: pd.DataFrame, filename: str, label: str) -> None:
    st.download_button(label, df.to_csv(index=False).encode("utf-8-sig"), filename, "text/csv")


def admin_only() -> None:
    if not is_admin():
        st.error("この画面は admin のみ利用できます。")
        st.stop()


def paper_payload_from_row(row: pd.Series) -> Dict[str, Any]:
    return {
        "title": safe_text(row.get("title")),
        "authors": safe_text(row.get("authors")),
        "publication_year": to_int(row.get("publication_year"), None),
        "journal": safe_text(row.get("journal")),
        "doi": safe_text(row.get("doi")),
        "url": safe_text(row.get("url")),
        "source_type": safe_text(row.get("source_type")) or "paper",
        "beginner_summary": safe_text(row.get("beginner_summary")),
        "detailed_summary": safe_text(row.get("detailed_summary")),
        "reliability": safe_text(row.get("reliability")) or "medium",
        "notes": safe_text(row.get("notes")),
        "is_active": bool(row.get("is_active", True)),
    }


def card_payload_from_row(row: pd.Series) -> Dict[str, Any]:
    return {
        "paper_id": safe_text(row.get("paper_id")),
        "theme": safe_text(row.get("theme")),
        "subtheme": safe_text(row.get("subtheme")),
        "title": safe_text(row.get("title")),
        "simple_explanation": safe_text(row.get("simple_explanation")),
        "detailed_explanation": safe_text(row.get("detailed_explanation")),
        "caution": safe_text(row.get("caution")),
        "tags": get_list(row.get("tags")),
        "importance": to_int(row.get("importance"), 3),
        "is_featured": bool(row.get("is_featured", False)),
    }


def render_header() -> None:
    st.title(f"🌱 {APP_TITLE}")
    top1, top2 = st.columns([4, 1])
    with top1:
        st.caption(f"ログイン中: {st.session_state.get('display_name')} / {role_label(st.session_state.get('user_role'))}")
    with top2:
        if st.button("ログアウト", use_container_width=True):
            logout()


ensure_login()
render_header()

theme_master = fetch_theme_master()
theme_options = ["すべて"] + [x["theme"] for x in theme_master]
papers = fetch_papers(active_only=False)
cards = fetch_cards()

menu_items = ["ホーム", "知見カード一覧", "論文一覧"]
if is_admin():
    menu_items += [
        "管理者：論文登録",
        "管理者：論文編集",
        "管理者：知見カード登録",
        "管理者：知見カード編集",
        "管理者：CSV一括インポート",
        "管理者：ユーザー管理",
    ]
menu_items.append("CSVテンプレート")

menu = st.sidebar.radio("メニュー", menu_items)

if menu == "ホーム":
    active_papers = [p for p in papers if p.get("is_active", True)]
    featured_cards = [c for c in cards if c.get("is_featured")]
    c1, c2, c3 = st.columns(3)
    c1.metric("有効な論文数", len(active_papers))
    c2.metric("知見カード数", len(cards))
    c3.metric("テーマ数", len(theme_master))

    st.markdown("## このDBについて")
    st.write(
        "論文PDFそのものではなく、リンク・要約・初心者向け知見カードを管理するアプリです。"
    )

    st.markdown("## テーマ一覧")
    if theme_master:
        for tm in theme_master:
            st.write(f"- {tm['theme']}")

    st.markdown("## 注目カード")
    if featured_cards:
        for card in featured_cards[:5]:
            render_card(card)
    else:
        st.info("注目カードはまだありません。")

elif menu == "知見カード一覧":
    st.subheader("知見カード一覧")
    all_tags = sorted({tag for card in cards for tag in get_list(card.get("tags"))})
    f1, f2, f3, f4 = st.columns([2, 3, 3, 2])
    with f1:
        selected_theme = st.selectbox("テーマ", theme_options)
    with f2:
        keyword = st.text_input("キーワード")
    with f3:
        selected_tags = st.multiselect("タグ", all_tags)
    with f4:
        reliability = st.selectbox("信頼度", ["すべて", "high", "medium", "low"])

    filtered = []
    for card in cards:
        blob = " ".join([
            str(card.get("card_title", "")),
            str(card.get("simple_explanation", "")),
            str(card.get("detailed_explanation", "")),
            str(card.get("caution", "")),
            str(card.get("paper_title", "")),
            str(card.get("authors", "")),
            str(card.get("journal", "")),
            str(card.get("theme", "")),
            str(card.get("subtheme", "")),
            " ".join(get_list(card.get("tags"))),
        ]).lower()
        if selected_theme != "すべて" and card.get("theme") != selected_theme:
            continue
        if reliability != "すべて" and card.get("reliability") != reliability:
            continue
        if keyword and keyword.lower() not in blob:
            continue
        if selected_tags and not set(selected_tags).issubset(set(get_list(card.get("tags")))):
            continue
        filtered.append(card)

    st.caption(f"{len(filtered)} 件")
    if filtered:
        download_csv(cards_dataframe(filtered), "jatropha_knowledge_cards.csv", "CSVダウンロード")
        for card in filtered:
            render_card(card)
    else:
        st.warning("該当データがありません。")

elif menu == "論文一覧":
    st.subheader("論文一覧")
    active_only = st.checkbox("有効な論文のみ", value=True)
    keyword = st.text_input("タイトル・著者・掲載誌で検索")
    filtered = []
    for paper in papers:
        if active_only and not paper.get("is_active", True):
            continue
        blob = " ".join([
            str(paper.get("title", "")),
            str(paper.get("authors", "")),
            str(paper.get("journal", "")),
            str(paper.get("beginner_summary", "")),
            str(paper.get("detailed_summary", "")),
            str(paper.get("notes", "")),
        ]).lower()
        if keyword and keyword.lower() not in blob:
            continue
        filtered.append(paper)

    st.caption(f"{len(filtered)} 件")
    if filtered:
        download_csv(paper_dataframe(filtered), "jatropha_papers.csv", "CSVダウンロード")
        for paper in filtered:
            with st.container(border=True):
                st.subheader(paper.get("title") or "-")
                meta = [
                    paper.get("authors"),
                    str(paper.get("publication_year")) if paper.get("publication_year") else None,
                    paper.get("journal"),
                ]
                meta = [m for m in meta if m]
                if meta:
                    st.caption(" / ".join(meta))
                c1, c2, c3 = st.columns(3)
                c1.markdown(f"**種別:** {paper.get('source_type', '-')}")
                c2.markdown(f"**信頼度:** {reliability_badge(paper.get('reliability'))}")
                c3.markdown(f"**有効:** {'Yes' if paper.get('is_active', True) else 'No'}")
                if paper.get("doi"):
                    st.write(f"**DOI:** {paper['doi']}")
                if paper.get("url"):
                    st.markdown(f"[リンクを開く]({paper['url']})")
                if paper.get("beginner_summary"):
                    st.markdown("**初心者向け要約**")
                    st.write(paper.get("beginner_summary"))
                if paper.get("detailed_summary"):
                    with st.expander("詳細要約"):
                        st.write(paper.get("detailed_summary"))
                if paper.get("notes"):
                    with st.expander("メモ"):
                        st.write(paper.get("notes"))
    else:
        st.warning("該当データがありません。")

elif menu == "管理者：論文登録":
    admin_only()
    st.subheader("管理者：論文登録")
    with st.form("paper_create_form"):
        title = st.text_input("論文タイトル *")
        authors = st.text_input("著者")
        publication_year = st.text_input("発行年")
        journal = st.text_input("掲載誌")
        doi = st.text_input("DOI")
        url = st.text_input("リンク(URL) *")
        source_type = st.selectbox("種別", ["paper", "report", "website", "book", "other"])
        reliability = st.selectbox("信頼度", ["high", "medium", "low"], index=1)
        beginner_summary = st.text_area("初心者向け要約", height=120)
        detailed_summary = st.text_area("詳細要約", height=180)
        notes = st.text_area("メモ", height=120)
        is_active = st.checkbox("有効", value=True)
        submitted = st.form_submit_button("登録")
    if submitted:
        if not title.strip() or not url.strip():
            st.error("論文タイトルとURLは必須です。")
        else:
            payload = {
                "title": title.strip(),
                "authors": safe_text(authors),
                "publication_year": to_int(publication_year),
                "journal": safe_text(journal),
                "doi": safe_text(doi),
                "url": url.strip(),
                "source_type": source_type,
                "beginner_summary": safe_text(beginner_summary),
                "detailed_summary": safe_text(detailed_summary),
                "reliability": reliability,
                "notes": safe_text(notes),
                "is_active": is_active,
            }
            try:
                insert_paper(payload)
                st.success("登録しました。")
                st.rerun()
            except Exception as e:
                st.error(f"登録エラー: {e}")

elif menu == "管理者：論文編集":
    admin_only()
    st.subheader("管理者：論文編集")
    paper_map = {f"{p['title']} ({p.get('publication_year') or '-'})": p for p in papers}
    if not paper_map:
        st.info("論文がありません。")
    else:
        selected_label = st.selectbox("編集する論文", list(paper_map.keys()))
        paper = paper_map[selected_label]
        with st.form("paper_edit_form"):
            title = st.text_input("論文タイトル *", value=paper.get("title") or "")
            authors = st.text_input("著者", value=paper.get("authors") or "")
            publication_year = st.text_input("発行年", value=str(paper.get("publication_year") or ""))
            journal = st.text_input("掲載誌", value=paper.get("journal") or "")
            doi = st.text_input("DOI", value=paper.get("doi") or "")
            url = st.text_input("リンク(URL) *", value=paper.get("url") or "")
            source_type = st.selectbox(
                "種別",
                ["paper", "report", "website", "book", "other"],
                index=["paper", "report", "website", "book", "other"].index(paper.get("source_type") or "paper")
                if (paper.get("source_type") or "paper") in ["paper", "report", "website", "book", "other"] else 0,
            )
            reliability = st.selectbox(
                "信頼度",
                ["high", "medium", "low"],
                index=["high", "medium", "low"].index(paper.get("reliability") or "medium")
                if (paper.get("reliability") or "medium") in ["high", "medium", "low"] else 1,
            )
            beginner_summary = st.text_area("初心者向け要約", value=paper.get("beginner_summary") or "", height=120)
            detailed_summary = st.text_area("詳細要約", value=paper.get("detailed_summary") or "", height=180)
            notes = st.text_area("メモ", value=paper.get("notes") or "", height=120)
            is_active = st.checkbox("有効", value=paper.get("is_active", True))
            submitted = st.form_submit_button("更新")
        if submitted:
            payload = {
                "title": title.strip(),
                "authors": safe_text(authors),
                "publication_year": to_int(publication_year),
                "journal": safe_text(journal),
                "doi": safe_text(doi),
                "url": url.strip(),
                "source_type": source_type,
                "beginner_summary": safe_text(beginner_summary),
                "detailed_summary": safe_text(detailed_summary),
                "reliability": reliability,
                "notes": safe_text(notes),
                "is_active": is_active,
            }
            try:
                update_paper(paper["id"], payload)
                st.success("更新しました。")
                st.rerun()
            except Exception as e:
                st.error(f"更新エラー: {e}")

elif menu == "管理者：知見カード登録":
    admin_only()
    st.subheader("管理者：知見カード登録")
    active_papers = [p for p in papers if p.get("is_active", True)]
    if not active_papers:
        st.warning("先に論文を登録してください。")
        st.stop()
    paper_map = {f"{p['title']} ({p.get('publication_year') or '-'})": p["id"] for p in active_papers}
    theme_vals = [x["theme"] for x in theme_master] if theme_master else ["栽培"]
    with st.form("card_create_form"):
        paper_label = st.selectbox("紐づける論文 *", list(paper_map.keys()))
        theme = st.selectbox("テーマ *", theme_vals)
        subtheme = st.text_input("サブテーマ")
        card_title = st.text_input("カードタイトル *")
        simple_explanation = st.text_area("わかりやすい説明 *", height=140)
        detailed_explanation = st.text_area("詳しい説明", height=180)
        caution = st.text_area("注意点", height=100)
        tags_text = st.text_input("タグ（カンマ区切り）")
        importance = st.slider("重要度", 1, 5, 3)
        is_featured = st.checkbox("注目カードにする", value=False)
        submitted = st.form_submit_button("登録")
    if submitted:
        if not card_title.strip() or not simple_explanation.strip():
            st.error("カードタイトルとわかりやすい説明は必須です。")
        else:
            payload = {
                "paper_id": paper_map[paper_label],
                "theme": theme,
                "subtheme": safe_text(subtheme),
                "title": card_title.strip(),
                "simple_explanation": simple_explanation.strip(),
                "detailed_explanation": safe_text(detailed_explanation),
                "caution": safe_text(caution),
                "tags": get_list(tags_text),
                "importance": importance,
                "is_featured": is_featured,
            }
            try:
                insert_card(payload)
                st.success("登録しました。")
                st.rerun()
            except Exception as e:
                st.error(f"登録エラー: {e}")

elif menu == "管理者：知見カード編集":
    admin_only()
    st.subheader("管理者：知見カード編集")
    if not cards:
        st.info("知見カードがありません。")
    else:
        labels = {f"{c.get('card_title')} / {c.get('theme')} / {c.get('paper_title')}": c for c in cards}
        selected_label = st.selectbox("編集する知見カード", list(labels.keys()))
        card = labels[selected_label]
        active_papers = [p for p in papers if p.get("is_active", True)]
        paper_options = {f"{p['title']} ({p.get('publication_year') or '-'})": p["id"] for p in active_papers}
        current_paper_label = next((k for k, v in paper_options.items() if v == card.get("paper_id")), list(paper_options.keys())[0])
        theme_vals = [x["theme"] for x in theme_master] if theme_master else [card.get("theme") or "栽培"]
        theme_default = theme_vals.index(card.get("theme")) if card.get("theme") in theme_vals else 0
        with st.form("card_edit_form"):
            paper_label = st.selectbox("紐づける論文 *", list(paper_options.keys()), index=list(paper_options.keys()).index(current_paper_label))
            theme = st.selectbox("テーマ *", theme_vals, index=theme_default)
            subtheme = st.text_input("サブテーマ", value=card.get("subtheme") or "")
            card_title = st.text_input("カードタイトル *", value=card.get("card_title") or "")
            simple_explanation = st.text_area("わかりやすい説明 *", value=card.get("simple_explanation") or "", height=140)
            detailed_explanation = st.text_area("詳しい説明", value=card.get("detailed_explanation") or "", height=180)
            caution = st.text_area("注意点", value=card.get("caution") or "", height=100)
            tags_text = st.text_input("タグ（カンマ区切り）", value=", ".join(get_list(card.get("tags"))))
            importance = st.slider("重要度", 1, 5, int(card.get("importance") or 3))
            is_featured = st.checkbox("注目カードにする", value=bool(card.get("is_featured")))
            submitted = st.form_submit_button("更新")
        if submitted:
            payload = {
                "paper_id": paper_options[paper_label],
                "theme": theme,
                "subtheme": safe_text(subtheme),
                "title": card_title.strip(),
                "simple_explanation": simple_explanation.strip(),
                "detailed_explanation": safe_text(detailed_explanation),
                "caution": safe_text(caution),
                "tags": get_list(tags_text),
                "importance": importance,
                "is_featured": is_featured,
            }
            try:
                update_card(card["knowledge_card_id"], payload)
                st.success("更新しました。")
                st.rerun()
            except Exception as e:
                st.error(f"更新エラー: {e}")

elif menu == "管理者：CSV一括インポート":
    admin_only()
    st.subheader("管理者：CSV一括インポート")
    tab1, tab2 = st.tabs(["papers", "knowledge_cards"])

    with tab1:
        st.markdown("**必須列:** title, url")
        upload = st.file_uploader("papers CSV", type=["csv"], key="papers_csv")
        if upload is not None:
            df = pd.read_csv(upload).fillna("")
            st.dataframe(df, use_container_width=True)
            if st.button("papers を一括登録", key="import_papers"):
                success = 0
                errors = []
                for idx, row in df.iterrows():
                    payload = paper_payload_from_row(row)
                    if not payload["title"] or not payload["url"]:
                        errors.append(f"行 {idx + 2}: title と url は必須です。")
                        continue
                    try:
                        insert_paper(payload)
                        success += 1
                    except Exception as e:
                        errors.append(f"行 {idx + 2}: {e}")
                st.success(f"登録成功: {success} 件")
                if errors:
                    st.error("\n".join(errors[:20]))

    with tab2:
        st.markdown("**必須列:** paper_id, theme, title, simple_explanation")
        upload = st.file_uploader("knowledge_cards CSV", type=["csv"], key="cards_csv")
        if upload is not None:
            df = pd.read_csv(upload).fillna("")
            st.dataframe(df, use_container_width=True)
            if st.button("knowledge_cards を一括登録", key="import_cards"):
                success = 0
                errors = []
                for idx, row in df.iterrows():
                    payload = card_payload_from_row(row)
                    missing = [k for k in ["paper_id", "theme", "title", "simple_explanation"] if not payload.get(k)]
                    if missing:
                        errors.append(f"行 {idx + 2}: 必須列不足 -> {', '.join(missing)}")
                        continue
                    try:
                        insert_card(payload)
                        success += 1
                    except Exception as e:
                        errors.append(f"行 {idx + 2}: {e}")
                st.success(f"登録成功: {success} 件")
                if errors:
                    st.error("\n".join(errors[:20]))

elif menu == "管理者：ユーザー管理":
    admin_only()
    st.subheader("管理者：ユーザー管理")
    t1, t2 = st.tabs(["ユーザー作成", "既存ユーザー管理"])

    with t1:
        with st.form("create_user_form"):
            username = st.text_input("ユーザー名 *")
            display_name = st.text_input("表示名 *")
            role = st.selectbox("権限", ["admin", "viewer"], index=1)
            password = st.text_input("初期パスワード *", type="password")
            password2 = st.text_input("初期パスワード（確認） *", type="password")
            submitted = st.form_submit_button("ユーザー作成")
        if submitted:
            if not username.strip() or not display_name.strip() or not password:
                st.error("必須項目を入力してください。")
            elif password != password2:
                st.error("パスワードが一致しません。")
            else:
                try:
                    result = create_user(username.strip(), display_name.strip(), role, password)
                    if result.get("ok"):
                        st.success("ユーザーを作成しました。")
                        st.rerun()
                    else:
                        st.error(result.get("message") or "ユーザー作成に失敗しました。")
                except Exception as e:
                    st.error(f"作成エラー: {e}")

    with t2:
        users = fetch_users()
        if not users:
            st.info("ユーザーがいません。")
        else:
            user_map = {f"{u['username']} / {role_label(u['role'])}": u for u in users}
            selected = st.selectbox("対象ユーザー", list(user_map.keys()))
            u = user_map[selected]
            with st.form("manage_user_form"):
                st.text_input("ユーザー名", value=u.get("username") or "", disabled=True)
                st.text_input("表示名", value=u.get("display_name") or "", disabled=True)
                role = st.selectbox("権限", ["admin", "viewer"], index=["admin", "viewer"].index(u.get("role") or "viewer"))
                is_active = st.checkbox("有効", value=bool(u.get("is_active")))
                submitted_role = st.form_submit_button("権限/有効状態を更新")
            if submitted_role:
                try:
                    update_user_role(u["id"], role, is_active)
                    st.success("更新しました。")
                    st.rerun()
                except Exception as e:
                    st.error(f"更新エラー: {e}")

            st.markdown("### ロック解除")
            st.write(f"失敗回数: {u.get('failed_attempts', 0)}")
            st.write(f"locked_until: {u.get('locked_until') or '-'}")
            if st.button("ロック解除", key=f"unlock_{u['id']}"):
                try:
                    unlock_user(u["id"])
                    st.success("ロック解除しました。")
                    st.rerun()
                except Exception as e:
                    st.error(f"解除エラー: {e}")

            st.markdown("### パスワード再設定")
            with st.form("reset_password_form"):
                new_password = st.text_input("新しいパスワード", type="password")
                new_password2 = st.text_input("新しいパスワード（確認）", type="password")
                submitted_pw = st.form_submit_button("パスワード更新")
            if submitted_pw:
                if not new_password:
                    st.error("新しいパスワードを入力してください。")
                elif new_password != new_password2:
                    st.error("パスワードが一致しません。")
                else:
                    try:
                        result = reset_user_password(u["id"], new_password)
                        if result.get("ok"):
                            st.success("パスワードを更新しました。")
                        else:
                            st.error(result.get("message") or "更新に失敗しました。")
                    except Exception as e:
                        st.error(f"パスワード更新エラー: {e}")

            st.markdown("### ユーザー一覧")
            st.dataframe(users_dataframe(users), use_container_width=True)

elif menu == "CSVテンプレート":
    st.subheader("CSVテンプレート")
    papers_sample = pd.DataFrame([
        {
            "title": "Sample Jatropha Paper",
            "authors": "Author A; Author B",
            "publication_year": 2024,
            "journal": "Sample Journal",
            "doi": "10.0000/sample-doi",
            "url": "https://example.com/jatropha-paper",
            "source_type": "paper",
            "beginner_summary": "初心者向け要約",
            "detailed_summary": "詳細要約",
            "reliability": "medium",
            "notes": "メモ",
            "is_active": True,
        }
    ])
    st.markdown("### papers 用")
    st.dataframe(papers_sample, use_container_width=True)
    download_csv(papers_sample, "papers_template.csv", "papers テンプレDL")

    cards_sample = pd.DataFrame([
        {
            "paper_id": "papers登録後のid",
            "theme": "栽培",
            "subtheme": "基本特性",
            "title": "ジャトロファはどんな植物か",
            "simple_explanation": "初心者向け説明",
            "detailed_explanation": "詳しい説明",
            "caution": "注意点",
            "tags": "栽培, 初心者向け, 基本",
            "importance": 5,
            "is_featured": True,
        }
    ])
    st.markdown("### knowledge_cards 用")
    st.dataframe(cards_sample, use_container_width=True)
    download_csv(cards_sample, "knowledge_cards_template.csv", "knowledge_cards テンプレDL")
