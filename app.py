import pandas as pd
import streamlit as st
from postgrest.exceptions import APIError
from supabase import Client, create_client

APP_TITLE = st.secrets.get("APP_TITLE", "Jatropha Knowledge DB")

st.set_page_config(
    page_title=APP_TITLE,
    page_icon="🌱",
    layout="wide"
)

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_ANON_KEY = st.secrets["SUPABASE_ANON_KEY"]

supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

if "auth_session" not in st.session_state:
    st.session_state.auth_session = None
if "user_profile" not in st.session_state:
    st.session_state.user_profile = None


def get_text_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    if isinstance(value, str):
        return [x.strip() for x in value.split(",") if x.strip()]
    return []


def normalize_int(value, default=None):
    try:
        if value is None or value == "":
            return default
        return int(value)
    except Exception:
        return default


def to_bool(value, default=False):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        v = value.strip().lower()
        return v in ["1", "true", "yes", "y", "t"]
    return default


def badge_reliability(value: str) -> str:
    if value == "high":
        return "🟢 high"
    if value == "medium":
        return "🟡 medium"
    if value == "low":
        return "🔴 low"
    return value or "-"


def dataframe_download(df: pd.DataFrame, filename: str, label: str):
    csv_bytes = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label=label,
        data=csv_bytes,
        file_name=filename,
        mime="text/csv"
    )


def is_logged_in() -> bool:
    return st.session_state.auth_session is not None


def is_admin() -> bool:
    profile = st.session_state.user_profile or {}
    return profile.get("role") == "admin" and profile.get("is_active", True)


def load_my_profile():
    try:
        user_res = supabase.auth.get_user()
        if not user_res or not user_res.user:
            st.session_state.user_profile = None
            return None

        uid = user_res.user.id
        res = (
            supabase.table("jatropha_profiles")
            .select("*")
            .eq("id", uid)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        profile = rows[0] if rows else None
        st.session_state.user_profile = profile
        return profile
    except Exception:
        st.session_state.user_profile = None
        return None


def login(email: str, password: str):
    res = supabase.auth.sign_in_with_password(
        {
            "email": email,
            "password": password,
        }
    )
    st.session_state.auth_session = res.session
    load_my_profile()


def signup(email: str, password: str, display_name: str):
    res = supabase.auth.sign_up(
        {
            "email": email,
            "password": password,
            "options": {
                "data": {
                    "display_name": display_name
                }
            }
        }
    )
    st.session_state.auth_session = res.session
    load_my_profile()


def logout():
    try:
        supabase.auth.sign_out()
    except Exception:
        pass
    st.session_state.auth_session = None
    st.session_state.user_profile = None
    st.rerun()


def fetch_theme_master():
    res = (
        supabase.table("jatropha_theme_master")
        .select("*")
        .eq("is_active", True)
        .order("sort_order")
        .execute()
    )
    return res.data or []


def fetch_papers(active_only=False):
    query = supabase.table("jatropha_papers").select("*").order("publication_year", desc=True)
    if active_only:
        query = query.eq("is_active", True)
    res = query.execute()
    return res.data or []


def fetch_cards():
    res = (
        supabase.table("jatropha_v_knowledge_cards")
        .select("*")
        .order("importance", desc=True)
        .execute()
    )
    return res.data or []


def fetch_profiles():
    res = (
        supabase.table("jatropha_profiles")
        .select("*")
        .order("created_at", desc=False)
        .execute()
    )
    return res.data or []


def insert_paper(payload):
    return supabase.table("jatropha_papers").insert(payload).execute()


def update_paper(paper_id, payload):
    return supabase.table("jatropha_papers").update(payload).eq("id", paper_id).execute()


def insert_card(payload):
    return supabase.table("jatropha_knowledge_cards").insert(payload).execute()


def update_card(card_id, payload):
    return supabase.table("jatropha_knowledge_cards").update(payload).eq("id", card_id).execute()


def update_profile(profile_id, payload):
    return supabase.table("jatropha_profiles").update(payload).eq("id", profile_id).execute()


def render_card(card):
    with st.container(border=True):
        left, right = st.columns([4, 1])

        with left:
            st.subheader(card.get("card_title", "-"))
            st.caption(
                f"テーマ: {card.get('theme', '-')}"
                + (f" / サブテーマ: {card.get('subtheme')}" if card.get("subtheme") else "")
            )

        with right:
            st.markdown(f"**重要度:** {card.get('importance', '-')}")
            st.markdown(f"**信頼度:** {badge_reliability(card.get('reliability'))}")

        st.markdown("**わかりやすい説明**")
        st.write(card.get("simple_explanation") or "-")

        if card.get("detailed_explanation"):
            with st.expander("詳しい説明"):
                st.write(card.get("detailed_explanation"))

        if card.get("caution"):
            st.markdown("**注意点**")
            st.warning(card.get("caution"))

        tags = get_text_list(card.get("tags"))
        if tags:
            st.markdown("**タグ**")
            st.write(" / ".join(tags))

        st.markdown("---")
        st.markdown("**出典**")
        st.write(f"**論文タイトル:** {card.get('paper_title', '-')}")
        meta = []
        if card.get("authors"):
            meta.append(str(card.get("authors")))
        if card.get("publication_year"):
            meta.append(str(card.get("publication_year")))
        if card.get("journal"):
            meta.append(str(card.get("journal")))
        if meta:
            st.caption(" / ".join(meta))

        if card.get("url"):
            st.markdown(f"[元リンクを開く]({card['url']})")


def import_papers_csv(df):
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
            "is_active": to_bool(row.get("is_active"), True),
            "created_by": st.session_state.user_profile["id"],
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


def import_cards_csv(df):
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

        payload = {
            "paper_id": paper_rows[0]["id"],
            "theme": theme,
            "subtheme": str(row.get("subtheme")).strip() if pd.notna(row.get("subtheme")) else None,
            "title": title,
            "simple_explanation": simple_explanation,
            "detailed_explanation": str(row.get("detailed_explanation")).strip() if pd.notna(row.get("detailed_explanation")) else None,
            "caution": str(row.get("caution")).strip() if pd.notna(row.get("caution")) else None,
            "tags": get_text_list(row.get("tags")),
            "importance": normalize_int(row.get("importance"), 3),
            "is_featured": to_bool(row.get("is_featured"), False),
            "is_active": to_bool(row.get("is_active"), True),
            "created_by": st.session_state.user_profile["id"],
        }

        existing = (
            supabase.table("jatropha_knowledge_cards")
            .select("id")
            .eq("paper_id", payload["paper_id"])
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


def login_screen():
    st.title(APP_TITLE)
    tab_login, tab_signup = st.tabs(["Login", "Sign up"])

    with tab_login:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        if st.button("Login", key="login_btn", type="primary"):
            try:
                login(email.strip(), password)
                if st.session_state.user_profile and st.session_state.user_profile.get("is_active", True):
                    st.success("Logged in")
                    st.rerun()
                st.error("Profile not found or inactive.")
            except APIError as e:
                st.error(str(e))
            except Exception as e:
                st.error(repr(e))

    with tab_signup:
        email = st.text_input("Email", key="signup_email")
        password = st.text_input("Password", type="password", key="signup_password")
        display_name = st.text_input("Display name", key="signup_display_name")
        if st.button("Create account", key="signup_btn"):
            try:
                signup(email.strip(), password, display_name.strip())
                st.success("Account created. If email confirmation is enabled, confirm it first.")
            except APIError as e:
                st.error(str(e))
            except Exception as e:
                st.error(repr(e))


if not is_logged_in():
    login_screen()
    st.stop()

profile = load_my_profile()
if not profile:
    st.error("Profile not found.")
    st.stop()

if not profile.get("is_active", True):
    st.error("Your account is inactive.")
    st.stop()

with st.sidebar:
    st.markdown(f"**User:** {profile.get('display_name') or profile.get('email')}")
    st.markdown(f"**Role:** {profile.get('role')}")
    if st.button("Logout"):
        logout()

    menu = ["ホーム", "知見カード一覧", "論文一覧", "自分のプロフィール"]
    if is_admin():
        menu += [
            "管理者：論文登録",
            "管理者：論文編集",
            "管理者：知見カード登録",
            "管理者：知見カード編集",
            "管理者：CSV一括取込",
            "管理者：ユーザー管理",
        ]
    selected = st.radio("メニュー", menu)

st.title(APP_TITLE)
st.caption("Supabase Auth + RLS version")

theme_master = fetch_theme_master()
theme_options = ["すべて"] + [x["theme"] for x in theme_master]
papers = fetch_papers(active_only=False)
cards = fetch_cards()

if selected == "ホーム":
    st.write("ジャトロファ初心者向けナレッジベースです。")
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

elif selected == "自分のプロフィール":
    st.subheader("My profile")
    st.json(profile)

elif selected == "知見カード一覧":
    all_tags = sorted(list({tag for c in cards for tag in get_text_list(c.get("tags"))}))

    c1, c2, c3, c4 = st.columns(4)
    theme = c1.selectbox("テーマ", theme_options)
    keyword = c2.text_input("キーワード")
    tags = c3.multiselect("タグ", all_tags)
    reliability = c4.selectbox("信頼度", ["すべて", "high", "medium", "low"], index=0)

    filtered = []
    for c in cards:
        blob = " ".join([
            str(c.get("card_title", "")),
            str(c.get("simple_explanation", "")),
            str(c.get("paper_title", "")),
            str(c.get("theme", "")),
            " ".join(get_text_list(c.get("tags"))),
        ]).lower()

        if theme != "すべて" and c.get("theme") != theme:
            continue
        if reliability != "すべて" and c.get("reliability") != reliability:
            continue
        if keyword and keyword.lower() not in blob:
            continue
        if tags and not set(tags).issubset(set(get_text_list(c.get("tags")))):
            continue
        filtered.append(c)

    st.caption(f"該当件数: {len(filtered)} 件")
    if filtered:
        dataframe_download(pd.DataFrame(filtered), "jatropha_cards.csv", "CSVダウンロード")
        for c in filtered:
            render_card(c)
    else:
        st.warning("該当する知見カードがありません。")

elif selected == "論文一覧":
    keyword = st.text_input("検索")
    active_only = st.checkbox("有効な論文のみ表示", value=True)

    filtered = []
    for p in papers:
        if active_only and not p.get("is_active", True):
            continue

        blob = " ".join([
            str(p.get("title", "")),
            str(p.get("authors", "")),
            str(p.get("journal", "")),
            str(p.get("beginner_summary", "")),
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
                meta = []
                if p.get("authors"):
                    meta.append(str(p.get("authors")))
                if p.get("publication_year"):
                    meta.append(str(p.get("publication_year")))
                if p.get("journal"):
                    meta.append(str(p.get("journal")))
                if meta:
                    st.caption(" / ".join(meta))

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

elif selected == "管理者：論文登録":
    if not is_admin():
        st.error("admin only")
        st.stop()

    with st.form("paper_form"):
        title = st.text_input("論文タイトル *")
        authors = st.text_input("著者")
        publication_year = st.text_input("発行年")
        journal = st.text_input("掲載誌")
        doi = st.text_input("DOI")
        url = st.text_input("リンク(URL) *")
        source_type = st.selectbox("種別", ["paper", "report", "website", "book", "other"])
        reliability = st.selectbox("信頼度", ["high", "medium", "low"], index=1)
        beginner_summary = st.text_area("初心者向け要約")
        detailed_summary = st.text_area("詳細要約")
        notes = st.text_area("メモ")
        is_active = st.checkbox("有効", value=True)
        submitted = st.form_submit_button("登録")

    if submitted:
        payload = {
            "title": title.strip(),
            "authors": authors.strip() or None,
            "publication_year": normalize_int(publication_year, None),
            "journal": journal.strip() or None,
            "doi": doi.strip() or None,
            "url": url.strip(),
            "source_type": source_type,
            "beginner_summary": beginner_summary.strip() or None,
            "detailed_summary": detailed_summary.strip() or None,
            "reliability": reliability,
            "notes": notes.strip() or None,
            "is_active": is_active,
            "created_by": profile["id"],
        }
        try:
            insert_paper(payload)
            st.success("登録しました")
            st.rerun()
        except Exception as e:
            st.error(repr(e))

elif selected == "管理者：論文編集":
    if not is_admin():
        st.error("admin only")
        st.stop()

    if not papers:
        st.info("論文がありません。")
        st.stop()

    options = {f"{p['title']} | {p['id']}": p for p in papers}
    label = st.selectbox("編集する論文", list(options.keys()))
    p = options[label]

    source_type_value = p.get("source_type", "paper")
    if source_type_value not in ["paper", "report", "website", "book", "other"]:
        source_type_value = "paper"

    reliability_value = p.get("reliability", "medium")
    if reliability_value not in ["high", "medium", "low"]:
        reliability_value = "medium"

    with st.form("paper_edit_form"):
        title = st.text_input("論文タイトル", value=p.get("title", ""))
        authors = st.text_input("著者", value=p.get("authors") or "")
        publication_year = st.text_input(
            "発行年",
            value="" if p.get("publication_year") is None else str(p.get("publication_year"))
        )
        journal = st.text_input("掲載誌", value=p.get("journal") or "")
        doi = st.text_input("DOI", value=p.get("doi") or "")
        url = st.text_input("リンク", value=p.get("url") or "")
        source_type = st.selectbox(
            "種別",
            ["paper", "report", "website", "book", "other"],
            index=["paper", "report", "website", "book", "other"].index(source_type_value)
        )
        reliability = st.selectbox(
            "信頼度",
            ["high", "medium", "low"],
            index=["high", "medium", "low"].index(reliability_value)
        )
        beginner_summary = st.text_area("初心者向け要約", value=p.get("beginner_summary") or "")
        detailed_summary = st.text_area("詳細要約", value=p.get("detailed_summary") or "")
        notes = st.text_area("メモ", value=p.get("notes") or "")
        is_active = st.checkbox("有効", value=p.get("is_active", True))
        submitted = st.form_submit_button("更新")

    if submitted:
        payload = {
            "title": title.strip(),
            "authors": authors.strip() or None,
            "publication_year": normalize_int(publication_year, None),
            "journal": journal.strip() or None,
            "doi": doi.strip() or None,
            "url": url.strip(),
            "source_type": source_type,
            "reliability": reliability,
            "beginner_summary": beginner_summary.strip() or None,
            "detailed_summary": detailed_summary.strip() or None,
            "notes": notes.strip() or None,
            "is_active": is_active,
        }
        try:
            update_paper(p["id"], payload)
            st.success("更新しました")
            st.rerun()
        except Exception as e:
            st.error(repr(e))

elif selected == "管理者：知見カード登録":
    if not is_admin():
        st.error("admin only")
        st.stop()

    active_papers = fetch_papers(active_only=True)
    if not active_papers:
        st.info("先に論文を登録してください。")
        st.stop()

    paper_map = {f"{p['title']} ({p.get('publication_year') or '-'})": p["id"] for p in active_papers}
    theme_values = [x["theme"] for x in theme_master] if theme_master else ["栽培"]

    with st.form("card_form"):
        paper_label = st.selectbox("紐づけ論文", list(paper_map.keys()))
        theme = st.selectbox("テーマ", theme_values)
        subtheme = st.text_input("サブテーマ")
        title = st.text_input("カードタイトル")
        simple_explanation = st.text_area("わかりやすい説明")
        detailed_explanation = st.text_area("詳しい説明")
        caution = st.text_area("注意点")
        tags_text = st.text_input("タグ（カンマ区切り）")
        importance = st.slider("重要度", 1, 5, 3)
        is_featured = st.checkbox("注目カード")
        is_active = st.checkbox("有効", value=True)
        submitted = st.form_submit_button("登録")

    if submitted:
        payload = {
            "paper_id": paper_map[paper_label],
            "theme": theme,
            "subtheme": subtheme.strip() or None,
            "title": title.strip(),
            "simple_explanation": simple_explanation.strip(),
            "detailed_explanation": detailed_explanation.strip() or None,
            "caution": caution.strip() or None,
            "tags": get_text_list(tags_text),
            "importance": importance,
            "is_featured": is_featured,
            "is_active": is_active,
            "created_by": profile["id"],
        }
        try:
            insert_card(payload)
            st.success("登録しました")
            st.rerun()
        except Exception as e:
            st.error(repr(e))

elif selected == "管理者：知見カード編集":
    if not is_admin():
        st.error("admin only")
        st.stop()

    raw_cards = (
        supabase.table("jatropha_knowledge_cards")
        .select("*")
        .order("created_at", desc=True)
        .execute()
    ).data or []

    if not raw_cards:
        st.info("知見カードがありません。")
        st.stop()

    theme_values = [x["theme"] for x in theme_master] if theme_master else ["栽培"]
    options = {f"{r['title']} | {r['id']}": r for r in raw_cards}
    label = st.selectbox("編集するカード", list(options.keys()))
    c = options[label]

    theme_value = c.get("theme", theme_values[0] if theme_values else "栽培")
    if theme_value not in theme_values:
        theme_value = theme_values[0]

    with st.form("card_edit_form"):
        theme = st.selectbox("テーマ", theme_values, index=theme_values.index(theme_value))
        subtheme = st.text_input("サブテーマ", value=c.get("subtheme") or "")
        title = st.text_input("カードタイトル", value=c.get("title") or "")
        simple_explanation = st.text_area("わかりやすい説明", value=c.get("simple_explanation") or "")
        detailed_explanation = st.text_area("詳しい説明", value=c.get("detailed_explanation") or "")
        caution = st.text_area("注意点", value=c.get("caution") or "")
        tags_text = st.text_input("タグ", value=", ".join(get_text_list(c.get("tags"))))
        importance = st.slider("重要度", 1, 5, int(c.get("importance") or 3))
        is_featured = st.checkbox("注目カード", value=c.get("is_featured", False))
        is_active = st.checkbox("有効", value=c.get("is_active", True))
        submitted = st.form_submit_button("更新")

    if submitted:
        payload = {
            "theme": theme,
            "subtheme": subtheme.strip() or None,
            "title": title.strip(),
            "simple_explanation": simple_explanation.strip(),
            "detailed_explanation": detailed_explanation.strip() or None,
            "caution": caution.strip() or None,
            "tags": get_text_list(tags_text),
            "importance": importance,
            "is_featured": is_featured,
            "is_active": is_active,
        }
        try:
            update_card(c["id"], payload)
            st.success("更新しました")
            st.rerun()
        except Exception as e:
            st.error(repr(e))

elif selected == "管理者：CSV一括取込":
    if not is_admin():
        st.error("admin only")
        st.stop()

    tab1, tab2, tab3 = st.tabs(["papers CSV", "cards CSV", "サンプルDL"])

    with tab1:
        up = st.file_uploader("papers CSV", type=["csv"], key="papers_csv")
        if up is not None:
            df = pd.read_csv(up)
            st.dataframe(df, use_container_width=True)
            if st.button("papers CSV 取込"):
                try:
                    imported, updated = import_papers_csv(df)
                    st.success(f"imported={imported}, updated={updated}")
                    st.rerun()
                except Exception as e:
                    st.error(repr(e))

    with tab2:
        up = st.file_uploader("cards CSV", type=["csv"], key="cards_csv")
        if up is not None:
            df = pd.read_csv(up)
            st.dataframe(df, use_container_width=True)
            if st.button("cards CSV 取込"):
                try:
                    imported, updated = import_cards_csv(df)
                    st.success(f"imported={imported}, updated={updated}")
                    st.rerun()
                except Exception as e:
                    st.error(repr(e))

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
        st.dataframe(papers_sample, use_container_width=True)
        dataframe_download(papers_sample, "jatropha_papers_sample.csv", "papers CSVサンプルDL")
        st.dataframe(cards_sample, use_container_width=True)
        dataframe_download(cards_sample, "jatropha_cards_sample.csv", "cards CSVサンプルDL")

elif selected == "管理者：ユーザー管理":
    if not is_admin():
        st.error("admin only")
        st.stop()

    profiles = fetch_profiles()
    if not profiles:
        st.info("ユーザーがいません。")
        st.stop()

    st.dataframe(pd.DataFrame(profiles), use_container_width=True)

    options = {f"{p.get('email')} | {p.get('id')}": p for p in profiles}
    label = st.selectbox("更新するユーザー", list(options.keys()))
    target = options[label]

    current_role = target.get("role", "viewer")
    if current_role not in ["viewer", "admin"]:
        current_role = "viewer"

    with st.form("profile_admin_form"):
        display_name = st.text_input("display_name", value=target.get("display_name") or "")
        role = st.selectbox("role", ["viewer", "admin"], index=["viewer", "admin"].index(current_role))
        is_active = st.checkbox("is_active", value=target.get("is_active", True))
        submitted = st.form_submit_button("更新")

    if submitted:
        try:
            update_profile(
                target["id"],
                {
                    "display_name": display_name.strip() or None,
                    "role": role,
                    "is_active": is_active,
                }
            )
            st.success("更新しました")
            st.rerun()
        except Exception as e:
            st.error(repr(e))
