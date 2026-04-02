import streamlit as st
from supabase import create_client
from postgrest.exceptions import APIError

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

st.title("Login Test")

if "user" not in st.session_state:
    st.session_state.user = None

if not st.session_state.user:
    username = st.text_input("username")
    password = st.text_input("password", type="password")

    if st.button("login"):
        try:
            res = supabase.rpc(
                "app_login",
                {
                    "p_username": username,
                    "p_password": password,
                }
            ).execute()

            st.write("RPC raw result:", res.data)

            if res.data and res.data[0]["ok"]:
                st.session_state.user = res.data[0]
                st.success("ログイン成功")
                st.rerun()
            else:
                st.error("ログイン失敗")

        except APIError as e:
            st.error("Supabase RPC error")
            st.code(str(e))
            try:
                st.json(e.json())
            except Exception:
                pass
        except Exception as e:
            st.error("Unexpected error")
            st.code(repr(e))

else:
    st.success(f"ようこそ {st.session_state.user['display_name']}")
    st.write(f"role: {st.session_state.user['role']}")

    if st.button("logout"):
        st.session_state.user = None
        st.rerun()
