import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime

# =========================================================
# Page Config
# =========================================================
st.set_page_config(
    page_title="Jatropha Knowledge DB",
    page_icon="🌱",
    layout="wide"
)

# =========================================================
# Secrets / Supabase
# =========================================================
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# =========================================================
# Helpers
# =========================================================
def get_text_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
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


def badge_reliability(value: str) -> str:
    if value == "high":
        return "🟢 high"
    if value == "medium":
        return "🟡 medium"
    if value == "low":
        return "🔴 low"
    return value or "-"


def insert_paper(data: dict):
    return supabase.table("papers").insert(data).execute()


def update_paper(paper_id: str, data: dict):
    return supabase.table("papers").update(data).eq("id", paper_id).execute()


def fetch_papers(active_only=True):
    query = supabase.table("papers").select("*").order("publication_year", desc=True)
    if active_only:
        query = query.eq("is_active", True)
    res = query.execute()
    return res.data if res.data else []


def fetch_theme_master():
    res = (
        supabase.table("theme_master")
        .select("*")
        .eq("is_active", True)
        .order("sort_order")
        .execute()
    )
    return res.data if res.data else []


def fetch_knowledge_cards():
    res = (
        supabase.table("v_knowledge_cards")
        .select("*")
        .order("importance", desc=True)
        .execute()
    )
    return res.data if res.data else []


def insert_knowledge_card(data: dict):
    return supabase.table("knowledge_cards").insert(data).execute()


def update_knowledge_card(card_id: str, data: dict):
    return supabase.table("knowledge_cards").update(data).eq("id", card_id).execute()


def dataframe_download(df: pd.DataFrame, filename: str, label: str):
    csv = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label=label,
        data=csv,
        file_name=filename,
        mime="text/csv"
    )


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

        if selected_tags:
            if not set(selected_tags).issubset(set(card_tags)):
                continue

        filtered.append(c)

    return filtered


def render_card(c):
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

        if c.get("paper_beginner_summary"):
            with st.expander("論文の初心者向け要約"):
                st.write(c.get("paper_beginner_summary"))

        if c.get("paper_detailed_summary"):
            with st.expander("論文の詳細要約"):
                st.write(c.get("paper_detailed_summary"))


# =========================================================
# Title
# =========================================================
st.title("🌱 Jatropha Knowledge DB")
st.caption("ジャトロファ初心者向けナレッジベース")

# =========================================================
# Sidebar
# =========================================================
menu = st.sidebar.radio(
    "メニュー",
    [
        "ホーム",
        "知見カード一覧",
        "論文一覧",
        "管理者：論文登録",
        "管理者：知見カード登録",
        "CSV一括登録ガイド"
    ]
)

# =========================================================
# Data Load
# =========================================================
theme_master = fetch_theme_master()
theme_options = ["すべて"] + [x["theme"] for x in theme_master]

cards = fetch_knowledge_cards()
papers = fetch_papers(active_only=False)

# =========================================================
# Home
# =========================================================
if menu == "ホーム":
    st.markdown("## このDBの目的")
    st.write(
        """
        このアプリは、ジャトロファに関する論文・記事の内容を
        **初心者でもわかりやすい形で整理して保管する** ためのデータベースです。
        
        PDFそのものは保存せず、
        **リンク・要約・知見カード** を管理する設計です。
        """
    )

    col1, col2, col3 = st.columns(3)
    col1.metric("論文数", len([p for p in papers if p.get("is_active", True)]))
    col2.metric("知見カード数", len(cards))
    col3.metric("テーマ数", len(theme_master))

    st.markdown("## よくあるテーマ")
    if theme_master:
        for tm in theme_master:
            st.write(f"- {tm['theme']}")
    else:
        st.info("theme_master にテーマがまだ入っていません。")

    st.markdown("## 注目カード")
    featured_cards = [c for c in cards if c.get("is_featured")]
    if not featured_cards:
        st.info("注目カードはまだありません。")
    else:
        for c in featured_cards[:5]:
            render_card(c)

# =========================================================
# Knowledge Cards
# =========================================================
elif menu == "知見カード一覧":
    st.markdown("## 知見カード一覧")

    all_tags = sorted(
        list(
            {
                tag
                for c in cards
                for tag in get_text_list(c.get("tags"))
            }
        )
    )

    col1, col2, col3, col4 = st.columns([2, 3, 3, 2])

    with col1:
        selected_theme = st.selectbox("テーマ", theme_options, index=0)

    with col2:
        keyword = st.text_input("キーワード検索")

    with col3:
        selected_tags = st.multiselect("タグ", all_tags)

    with col4:
        reliability = st.selectbox("信頼度", ["すべて", "high", "medium", "low"], index=0)

    filtered_cards = filter_cards(cards, selected_theme, keyword, selected_tags, reliability)

    st.caption(f"該当件数: {len(filtered_cards)} 件")

    if filtered_cards:
        export_df = pd.DataFrame(filtered_cards)
        dataframe_download(export_df, "jatropha_knowledge_cards.csv", "CSVダウンロード")

        for c in filtered_cards:
            render_card(c)
    else:
        st.warning("該当する知見カードがありません。")

# =========================================================
# Papers
# =========================================================
elif menu == "論文一覧":
    st.markdown("## 論文一覧")

    active_only = st.checkbox("有効な論文のみ表示", value=True)
    paper_list = [p for p in papers if (p.get("is_active", True) if active_only else True)]

    keyword = st.text_input("タイトル・著者・掲載誌で検索", key="paper_search")

    filtered_papers = []
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
        filtered_papers.append(p)

    st.caption(f"該当件数: {len(filtered_papers)} 件")

    if filtered_papers:
        df = pd.DataFrame(filtered_papers)
        dataframe_download(df, "jatropha_papers.csv", "CSVダウンロード")

        for p in filtered_papers:
            with st.container(border=True):
                st.subheader(p.get("title", "-"))
                st.caption(
                    " / ".join(
                        [x for x in [
                            str(p.get("authors")) if p.get("authors") else "",
                            str(p.get("publication_year")) if p.get("publication_year") else "",
                            str(p.get("journal")) if p.get("journal") else "",
                        ] if x]
                    )
                )

                col1, col2, col3 = st.columns(3)
                col1.markdown(f"**種別:** {p.get('source_type', '-')}")
                col2.markdown(f"**信頼度:** {badge_reliability(p.get('reliability'))}")
                col3.markdown(f"**有効:** {'Yes' if p.get('is_active', True) else 'No'}")

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

# =========================================================
# Admin: Paper Registration
# =========================================================
elif menu == "管理者：論文登録":
    st.markdown("## 管理者：論文登録")

    st.info("※ この画面は service role key 前提で登録できます。")

    with st.form("paper_form"):
        title = st.text_input("論文タイトル *")
        authors = st.text_input("著者")
        publication_year = st.text_input("発行年")
        journal = st.text_input("掲載誌")
        doi = st.text_input("DOI")
        url = st.text_input("リンク(URL) *")

        source_type = st.selectbox(
            "種別",
            ["paper", "report", "website", "book", "other"],
            index=0
        )

        reliability = st.selectbox(
            "信頼度",
            ["high", "medium", "low"],
            index=1
        )

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
            }

            try:
                insert_paper(payload)
                st.success("論文を登録しました。")
                st.rerun()
            except Exception as e:
                st.error(f"登録エラー: {e}")

    st.markdown("---")
    st.markdown("### 登録済み論文")
    paper_df = pd.DataFrame(fetch_papers(active_only=False))
    if not paper_df.empty:
        st.dataframe(paper_df, use_container_width=True)
    else:
        st.info("論文データがありません。")

# =========================================================
# Admin: Knowledge Card Registration
# =========================================================
elif menu == "管理者：知見カード登録":
    st.markdown("## 管理者：知見カード登録")

    st.info("※ まず論文を登録してから、その論文に紐づく知見カードを作成します。")

    current_papers = fetch_papers(active_only=True)
    if not current_papers:
        st.warning("先に論文を登録してください。")
        st.stop()

    paper_map = {
        f"{p['title']} ({p.get('publication_year') or '-'})": p["id"]
        for p in current_papers
    }

    with st.form("card_form"):
        selected_paper_label = st.selectbox("紐づける論文 *", list(paper_map.keys()))
        theme = st.selectbox("テーマ *", [x["theme"] for x in theme_master] if theme_master else ["栽培"])
        subtheme = st.text_input("サブテーマ")
        card_title = st.text_input("カードタイトル *")
        simple_explanation = st.text_area("わかりやすい説明 *", height=140)
        detailed_explanation = st.text_area("詳しい説明", height=180)
        caution = st.text_area("注意点", height=100)
        tags_text = st.text_input("タグ（カンマ区切り）", placeholder="例: 毒性, 種子, 初心者向け")
        importance = st.slider("重要度", min_value=1, max_value=5, value=3)
        is_featured = st.checkbox("注目カードにする", value=False)

        submitted_card = st.form_submit_button("知見カードを登録")

    if submitted_card:
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
            }

            try:
                insert_knowledge_card(payload)
                st.success("知見カードを登録しました。")
                st.rerun()
            except Exception as e:
                st.error(f"登録エラー: {e}")

    st.markdown("---")
    st.markdown("### 登録済み知見カード")
    card_df = pd.DataFrame(fetch_knowledge_cards())
    if not card_df.empty:
        st.dataframe(card_df, use_container_width=True)
    else:
        st.info("知見カードがありません。")

# =========================================================
# CSV Guide
# =========================================================
elif menu == "CSV一括登録ガイド":
    st.markdown("## CSV一括登録ガイド")

    st.markdown("### papers 用CSV例")
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
    st.dataframe(papers_sample, use_container_width=True)
    dataframe_download(papers_sample, "papers_sample.csv", "papers CSVサンプルDL")

    st.markdown("### knowledge_cards 用CSV例")
    cards_sample = pd.DataFrame([
        {
            "paper_id": "先に papers を登録して取得したidを入れる",
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
    st.dataframe(cards_sample, use_container_width=True)
    dataframe_download(cards_sample, "knowledge_cards_sample.csv", "knowledge_cards CSVサンプルDL")

    st.markdown("### 補足")
    st.write(
        """
        - `paper_id` は `papers` テーブル登録後に付与されるIDです  
        - `tags` はカンマ区切りで管理し、登録時に配列へ変換する実装にしてもOKです  
        - 一括取込機能そのものも後から追加できます
        """
    )
