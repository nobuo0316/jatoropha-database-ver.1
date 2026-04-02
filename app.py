import hashlib
import json
from io import BytesIO
from typing import Dict, List, Optional
from urllib import error, parse, request

import pandas as pd
import streamlit as st

# Optional Excel engines
try:
    import openpyxl  # noqa: F401
    OPENPYXL_AVAILABLE = True
except Exception:
    OPENPYXL_AVAILABLE = False

try:
    import xlsxwriter  # noqa: F401
    XLSXWRITER_AVAILABLE = True
except Exception:
    XLSXWRITER_AVAILABLE = False

st.set_page_config(
    page_title="Wage Table Guide / 賃金テーブル説明ページ",
    page_icon="📘",
    layout="wide",
)

# =========================================================
# Master data
# =========================================================
GRADES: List[str] = ["G6", "G5B", "G5A", "G4", "G3", "G2"]
STEPS: List[int] = list(range(1, 50))
NEXT_GRADE: Dict[str, str] = {
    "G6": "G5B",
    "G5B": "G5A",
    "G5A": "G4",
    "G4": "G3",
    "G3": "G2",
    "G2": "",
}
DEFAULT_EMPLOYEE_COLUMNS = [
    "Employee ID",
    "Name",
    "Area",
    "Grade",
    "Step",
    "University Graduate",
    "Adjustment Allowance",
    "Taxable Allowance",
    "Non-Taxable Allowance",
    "Active",
]
DEFAULT_PARAMS = {
    "G6": {"base": 18000.0, "ap": 500.0, "pp": 1500.0},
    "G5B": {"base": 22000.0, "ap": 600.0, "pp": 1800.0},
    "G5A": {"base": 26000.0, "ap": 700.0, "pp": 2200.0},
    "G4": {"base": 32000.0, "ap": 800.0, "pp": 2800.0},
    "G3": {"base": 40000.0, "ap": 1000.0, "pp": 3500.0},
    "G2": {"base": 52000.0, "ap": 1200.0, "pp": 0.0},
}

AREAS: List[str] = ["Davao", "General Santos", "Tawi-Tawi", "Olutanga"]
AREA_LABELS = {
    "Davao": {"日本語": "ダバオ", "English": "Davao"},
    "General Santos": {"日本語": "ゼネサン", "English": "General Santos"},
    "Tawi-Tawi": {"日本語": "タウイタウイ", "English": "Tawi-Tawi"},
    "Olutanga": {"日本語": "オルタンガ", "English": "Olutanga"},
}
WORK_DAYS_PER_YEAR = 313
MONTHS_PER_YEAR = 12
DEFAULT_AREA_MIN_WAGES = {
    "Davao": 540.0,
    "General Santos": 460.0,
    "Tawi-Tawi": 386.0,
    "Olutanga": 464.0,
}

LANGUAGE_PACK = {
    "日本語": {
        "title": "賃金テーブル管理・説明ページ",
        "subtitle": "制度説明、図解、シミュレーション、名簿管理を1つにまとめたページです。",
        "login_title": "ログイン",
        "login_id": "ID",
        "login_password": "パスワード",
        "login_button": "ログイン",
        "logout_button": "ログアウト",
        "login_error": "IDまたはパスワードが違います。",
        "logged_in_as": "ログイン中",
        "tab_overview": "制度説明",
        "tab_diagram": "図で理解",
        "tab_table": "賃金テーブル",
        "tab_sim": "昇格シミュレーション",
        "tab_adjustment_calc": "調整手当計算",
        "tab_allowance_export": "手当込みエクスポート",
        "tab_employee": "従業員名簿",
        "tab_admin": "管理設定",
        "sidebar_currency": "通貨記号",
        "sidebar_decimals": "小数表示",
        "sidebar_example": "GS例",
        "overview_heading": "制度概要",
        "overview_text1": "本ページでは、Grade（グレード）と Step（ステップ）に基づく賃金テーブルを、日本語・英語の両方で説明・管理できます。",
        "overview_text2": "各社員には必ず Grade と Step があり、これを合わせて GS と表記します。例：G5A の Step 4 は G5A-S4 です。",
        "grade_axis": "横軸は Grade（G6～G2）、縦軸は Step（1～49）です。",
        "rule_heading": "基本ルール",
        "rule_ap": "AP（Annual Pay Raise）：毎年、同一グレード内で昇給する額です。",
        "rule_pp": "PP（Pay by Promotion）：昇格時に加算される昇給額です。",
        "rule_allow": "主な手当は、調整手当と大卒手当です。今後、必要に応じて追加可能です。",
        "rule_promo": "昇格時は、『現在給与 + 現在グレードの AP + 現在グレードの PP』を下回らないことを条件に、次グレードでその金額以上となる最も近い Step に移動します。",
        "grade_table": "グレード一覧",
        "grade": "グレード",
        "position": "役職イメージ",
        "next_grade": "次グレード",
        "glabel_G6": "平社員",
        "glabel_G5B": "シニアスタッフ",
        "glabel_G5A": "上位シニアスタッフ",
        "glabel_G4": "スーパーバイザー",
        "glabel_G3": "課長",
        "glabel_G2": "次長",
        "ap_pp_heading": "昇給ルール（AP / PP一覧）",
        "ap_label": "AP（毎年昇給）",
        "pp_label": "PP（昇格昇給）",
        "case_study_heading": "イメージしやすい例",
        "case_new_grad_title": "例1：新卒社員を採用した場合",
        "case_new_grad_text": "新卒社員は、例として G6-S1 からスタートします。その後、毎年 AP によって Step が1つずつ上がります。昇格時は、PP を加えた最低必要額を満たす次グレードの Step に移動します。",
        "case_mid_title": "例2：スーパーバイザーレベルの中途社員を採用した場合",
        "case_mid_text": "スーパーバイザーレベルの中途社員は、例として G4-S3 からスタートします。この場合も毎年 AP によって Step が上がり、昇格時には PP を加えた条件に基づいて次グレードの Step が決まります。",
        "case_note": "実際のスタート位置は、経験、スキル、採用条件に応じて決定されます。ここでは制度理解のための例を示しています。",
        "career_25_heading": "25年間のキャリア推移（モデルケース）",
        "career_newgrad_title": "新卒採用の場合（モデルケース）",
        "career_newgrad_text": "新卒社員は一般的に G6-S1 からスタートします。毎年、AP により Step が1段階ずつ上昇し、一定の評価および役割拡大に応じて上位 Grade へ昇格します。想定例として、入社時 G6-S1、5年目 G6-S5、6年目 G5B へ昇格、10年目 G5A へ昇格、15年目 G4 へ昇格、20年目 G3 へ昇格、25年目に G2 に到達するケースが考えられます。",
        "career_mid_title": "中途採用（スーパーバイザー相当）の場合",
        "career_mid_text": "スーパーバイザーレベルの中途社員は、G4帯からのスタートを想定します。初期 Grade が高いため、早期にマネジメント層へ移行する可能性があります。想定例として、入社時 G4-S3、3年目 G4-S5、4年目 G3 へ昇格、10年目 G2 へ昇格するケースが考えられます。",
        "career_note": "上記は制度理解のためのモデルケースです。実際の昇格・昇給は、評価、役割、組織方針に基づいて決定されます。",
        "career_diagram_heading": "キャリア推移イメージ（25年）",
        "diagram_heading1": "① Grade と Step の関係",
        "diagram_heading2": "② AP と PP の考え方",
        "diagram_heading3": "③ 昇格時の移動イメージ",
        "diagram_help1": "下の図では、横方向が Grade、縦方向が Step です。社員は必ずどこか1つの GS に所属します。",
        "diagram_help2": "AP は同じ Grade 内での毎年の昇給、PP は次の Grade へ上がるときの追加昇給です。",
        "diagram_help3": "昇格時は、最低必要額を満たす次グレードの最も近い Step に移動します。",
        "simple_example_text": "例：G5A-S4 の社員が昇格する場合、まず『現在給与 + AP + PP』で最低必要額を算出し、その金額以上となる G4 の最初の Step を探します。",
        "wage_heading": "賃金テーブル",
        "wage_caption": "値は直接編集できます。説明用にも管理用にも利用できます。",
        "table_view_mode": "表示モード",
        "table_mode_raw": "数値のみ",
        "table_mode_with_label": "GSラベル付き",
        "download_csv": "CSVをダウンロード",
        "download_excel": "Excelをダウンロード",
        "download_note": "必要に応じて、このまま CSV / Excel で配布できます。",
        "sim_heading": "昇格シミュレーション",
        "sim_detail_heading": "計算の内訳",
        "sim_explanation_heading": "計算結果の説明",
        "sim_item": "項目",
        "sim_amount": "金額",
        "sim_current_salary": "現在給与",
        "sim_target_salary": "昇格後基本給",
        "adjustment_calc_heading": "調整手当計算",
        "adjustment_calc_text": "CSVをアップロードすると、複数人分の調整手当を一括計算し、そのまま従業員名簿アップロード用CSVとしてダウンロードできます。",
        "adjustment_calc_employee_id": "社員ID",
        "adjustment_calc_name": "氏名",
        "adjustment_calc_area": "エリア",
        "adjustment_calc_target_grade": "新グレード",
        "adjustment_calc_current_basic": "現在の基本給",
        "adjustment_calc_current_total": "現在の総支給額",
        "adjustment_calc_other_allowance": "その他手当（維持する額）",
        "adjustment_calc_active": "在籍者として出力",
        "adjustment_calc_run": "CSVを一括計算",
        "adjustment_calc_result": "計算結果",
        "adjustment_calc_target_step": "適用Step",
        "adjustment_calc_new_basic": "新基本給",
        "adjustment_calc_university_allowance": "大卒手当",
        "adjustment_calc_required_adjustment": "必要な調整手当",
        "adjustment_calc_new_total": "新総支給額",
        "adjustment_calc_download": "一括計算結果CSVをダウンロード",
        "adjustment_calc_download_excel": "一括計算結果Excelをダウンロード",
        "adjustment_calc_step_logic": "Step決定ロジック",
        "adjustment_calc_adjustment_logic": "調整手当ロジック",
        "adjustment_calc_result_text": "出力ファイルはそのまま従業員名簿タブへアップロードできます。",
        "current_grade": "現在グレード",
        "current_step": "現在ステップ",
        "current_salary": "現在給与",
        "min_required": "昇格時の最低必要額",
        "promoted_grade": "昇格後グレード",
        "promoted_step": "昇格後ステップ",
        "promoted_salary": "昇格後基本給",
        "adjust_allowance": "調整手当",
        "univ_allowance": "大卒手当",
        "is_univ": "大卒対象",
        "other_allowance": "その他手当",
        "taxable_allowance": "課税手当",
        "non_taxable_allowance": "非課税手当",
        "final_salary": "最終支給額",
        "simulate": "シミュレーション実行",
        "no_next_grade": "これ以上の次グレードはありません。",
        "gs_before": "昇格前GS",
        "gs_after": "昇格後GS",
        "promotion_flow": "昇格の流れ",
        "step_search_result": "該当Stepの探索結果",
        "allowance_export_heading": "手当込み賃金テーブル",
        "allowance_export_text": "固定額の手当を加えた賃金テーブルを表示・エクスポートできます。",
        "adjustment_allowance_export": "調整手当（固定額）",
        "university_allowance_export": "大卒手当（固定額）",
        "other_allowance_export": "その他手当（固定額）",
        "include_adjustment_allowance": "調整手当を含める",
        "include_university_allowance": "大卒手当を含める",
        "include_other_allowance": "その他手当を含める",
        "export_with_allowances_csv": "手当込みCSVをダウンロード",
        "export_with_allowances_excel": "手当込みExcelをダウンロード",
        "employee_heading": "従業員名簿",
        "employee_text": "従業員名簿を CSV で読み込み、各従業員の基本給、手当、合計支給額を一覧化できます。",
        "employee_template_download": "従業員名簿テンプレートをダウンロード",
        "employee_upload": "従業員名簿CSVをアップロード",
        "employee_apply": "従業員名簿を反映",
        "employee_preview": "従業員名簿プレビュー",
        "employee_import_success": "従業員名簿を反映しました。",
        "employee_import_empty": "従業員名簿CSVを選択してください。",
        "employee_import_error": "従業員名簿CSVの形式が正しくありません。",
        "employee_export_csv": "従業員給与一覧CSVをダウンロード",
        "employee_export_excel": "従業員給与一覧Excelをダウンロード",
        "employee_id": "社員ID",
        "employee_name": "氏名",
        "employee_grade": "Grade",
        "employee_step": "Step",
        "employee_basic_pay": "基本給",
        "employee_university_flag": "大卒対象",
        "employee_adjustment_allowance": "調整手当",
        "employee_other_allowance": "その他手当",
        "employee_taxable_allowance": "課税手当",
        "employee_non_taxable_allowance": "非課税手当",
        "employee_university_allowance": "大卒手当",
        "employee_total_allowance": "手当合計",
        "employee_total_pay": "合計支給額",
        "employee_sss": "SSS（本人負担）",
        "employee_philhealth": "PhilHealth（本人負担）",
        "employee_pagibig": "HDMF / Pag-IBIG（本人負担）",
        "employee_taxable_income": "課税対象月額",
        "employee_withholding_tax": "源泉税",
        "employee_total_deductions": "控除合計",
        "employee_net_pay": "手取り額",
        "employee_net_note": "手取り額は、SSS・PhilHealth・HDMF/Pag-IBIG・BIR源泉税を反映した概算です。ローン控除、欠勤・遅刻控除、残業、夜勤、休日手当、非課税手当、13th month、税年末調整などは別途考慮が必要です。",
        "active_only": "在籍者のみ表示",
        "default_university_allowance": "名簿計算用の大卒手当（固定額）",
        "admin_heading": "管理設定",
        "admin_text": "ここで初期テーブルの自動生成ルールを変更できます。実際の賃金額が決まっている場合は、下のテーブルを直接編集してください。",
        "base_salary": "Step1基準額",
        "ap": "AP（毎年昇給額）",
        "pp": "PP（昇格昇給額）",
        "rebuild": "設定値でテーブル再生成",
        "reset": "初期値に戻す",
        "warning_rebuild": "再生成すると、現在の手動編集内容は上書きされます。",
        "success_rebuild": "テーブルを再生成して保存しました。",
        "success_reset": "初期値に戻して保存しました。",
        "csv_import_heading": "設定CSVインポート",
        "csv_import_text": "この画面の設定値（Step1基準額、AP、PP）をCSVで一括更新できます。反映後、賃金テーブルも自動で再生成され、Supabase に保存されます。",
        "csv_upload": "設定CSVファイルをアップロード",
        "csv_apply": "CSVを設定に反映",
        "csv_template_download": "設定CSVテンプレートをダウンロード",
        "csv_import_success": "CSVから設定値を更新し、賃金テーブルを再生成して保存しました。",
        "csv_import_error": "CSVの形式が正しくありません。Grade, Base, AP, PP 列が必要で、G6, G5B, G5A, G4, G3, G2 の6行が必要です。",
        "csv_import_empty": "CSVファイルを選択してください。",
        "csv_preview_heading": "CSVプレビュー",
        "currency_preview": "表示例",
        "excel_unavailable": "この環境ではExcel出力が使えません。CSVを使うか、requirements.txt に openpyxl または xlsxwriter を追加してください。",
        "supabase_status_ok": "Supabase接続: ON",
        "supabase_status_off": "Supabase接続: OFF（ローカル初期値を使用）",
        "supabase_save_error": "Supabase保存に失敗しました。",
        "admin_password": "管理用パスワード",
        "admin_unlock": "管理ロック解除",
        "admin_locked": "管理設定の変更にはパスワードが必要です。",
        "admin_unlocked": "管理ロックを解除しました。",
        "admin_password_error": "パスワードが違います。",
        "admin_only_upload_notice": "🔒 この操作は管理者のみ実行できます。一般ユーザーは閲覧のみ可能です。",
    },
    "English": {
        "title": "Wage Table Management & Explanation Page",
        "subtitle": "A page that combines system explanation, visual guides, simulation, and roster management.",
        "login_title": "Login",
        "login_id": "ID",
        "login_password": "Password",
        "login_button": "Login",
        "logout_button": "Logout",
        "login_error": "Incorrect ID or password.",
        "logged_in_as": "Logged in as",
        "tab_overview": "Overview",
        "tab_diagram": "Visual Guide",
        "tab_table": "Wage Table",
        "tab_sim": "Promotion Simulation",
        "tab_adjustment_calc": "Adjustment Allowance Calc",
        "tab_allowance_export": "Allowance Export",
        "tab_employee": "Employee Roster",
        "tab_admin": "Admin Settings",
        "sidebar_currency": "Currency symbol",
        "sidebar_decimals": "Decimal places",
        "sidebar_example": "GS Example",
        "overview_heading": "System Overview",
        "overview_text1": "This page explains and manages the wage table based on Grade and Step in both English and Japanese.",
        "overview_text2": "Each employee always has a Grade and a Step, abbreviated as GS. Example: G5A Step 4 is written as G5A-S4.",
        "grade_axis": "The horizontal axis is Grade (G6 to G2), and the vertical axis is Step (1 to 49).",
        "rule_heading": "Basic Rules",
        "rule_ap": "AP (Annual Pay Raise): the amount of annual raise within the same grade.",
        "rule_pp": "PP (Pay by Promotion): the additional increase applied upon promotion.",
        "rule_allow": "Main allowances are Adjustment Allowance and University Graduate Allowance. Additional allowances can be added later if needed.",
        "rule_promo": "Upon promotion, the new salary must not be lower than Current Salary + current grade AP + current grade PP. The employee moves to the closest step in the next grade that meets or exceeds that amount.",
        "grade_table": "Grade Reference",
        "grade": "Grade",
        "position": "Position Image",
        "next_grade": "Next Grade",
        "glabel_G6": "Staff",
        "glabel_G5B": "Senior Staff",
        "glabel_G5A": "Upper Senior Staff",
        "glabel_G4": "Supervisor",
        "glabel_G3": "Manager",
        "glabel_G2": "Deputy General Manager",
        "ap_pp_heading": "Raise Rules (AP / PP)",
        "ap_label": "AP (Annual Raise)",
        "pp_label": "PP (Promotion Raise)",
        "case_study_heading": "Easy-to-Understand Examples",
        "case_new_grad_title": "Case 1: When a new graduate is hired",
        "case_new_grad_text": "A new graduate may start at G6-S1. After that, the Step increases by AP every year. At promotion, the employee moves to the first Step in the next Grade that satisfies the minimum required amount including PP.",
        "case_mid_title": "Case 2: When a supervisor-level mid-career employee is hired",
        "case_mid_text": "A supervisor-level mid-career hire may start at G4-S3. In the same way, the Step increases every year through AP. At promotion, the employee moves to the first Step in the next Grade that satisfies the minimum required amount including PP.",
        "case_note": "The actual starting position depends on experience, skills, and hiring conditions. These are examples provided for easier understanding of the system.",
        "career_25_heading": "25-Year Career Progression (Model Cases)",
        "career_newgrad_title": "New Graduate Hire (Model Case)",
        "career_newgrad_text": "A new graduate typically starts at G6-S1. Every year, the Step increases by one level through AP, and the employee may be promoted to a higher Grade based on evaluation and increased responsibility. A sample path could be: Start at G6-S1, Year 5 at G6-S5, Year 6 promoted to G5B, Year 10 promoted to G5A, Year 15 promoted to G4, Year 20 promoted to G3, and Year 25 potentially reaching G2.",
        "career_mid_title": "Mid-Career Hire at Supervisor Level",
        "career_mid_text": "A mid-career employee hired at supervisor level may start in the G4 range. Because the initial Grade is higher, transition to management levels may occur sooner. A sample path could be: Start at G4-S3, Year 3 at G4-S5, Year 4 promoted to G3, and Year 10 promoted to G2.",
        "career_note": "These are model cases for explanation purposes. Actual salary increases and promotions are determined based on evaluation, role, and company policy.",
        "career_diagram_heading": "Career Progression Image (25 Years)",
        "diagram_heading1": "1) Relationship between Grade and Step",
        "diagram_heading2": "2) How AP and PP work",
        "diagram_heading3": "3) Promotion movement image",
        "diagram_help1": "In the chart below, Grade runs horizontally and Step runs vertically. Every employee always belongs to one GS position.",
        "diagram_help2": "AP means annual raise within the same grade. PP means the additional raise given when moving to the next grade.",
        "diagram_help3": "At promotion, the employee moves to the closest step in the next grade that meets the minimum required amount.",
        "simple_example_text": "Example: when an employee at G5A-S4 is promoted, first calculate Current Salary + AP + PP, then find the first Step in G4 that is equal to or higher than that threshold.",
        "wage_heading": "Wage Table",
        "wage_caption": "Values can be edited directly. The table can be used both for explanation and administration.",
        "table_view_mode": "View Mode",
        "table_mode_raw": "Raw Numbers",
        "table_mode_with_label": "With GS Labels",
        "download_csv": "Download CSV",
        "download_excel": "Download Excel",
        "download_note": "You can distribute this as CSV or Excel as needed.",
        "sim_heading": "Promotion Simulation",
        "sim_detail_heading": "Calculation Breakdown",
        "sim_explanation_heading": "Calculation Explanation",
        "sim_item": "Item",
        "sim_amount": "Amount",
        "sim_current_salary": "Current Salary",
        "sim_target_salary": "Promoted Base Salary",
        "adjustment_calc_heading": "Adjustment Allowance Calculation",
        "adjustment_calc_text": "Upload a CSV to calculate adjustment allowance for multiple employees at once, then download the result as a CSV ready for the employee roster upload tab.",
        "adjustment_calc_employee_id": "Employee ID",
        "adjustment_calc_name": "Name",
        "adjustment_calc_area": "Area",
        "adjustment_calc_target_grade": "New Grade",
        "adjustment_calc_current_basic": "Current Base Pay",
        "adjustment_calc_current_total": "Current Total Pay",
        "adjustment_calc_other_allowance": "Other Allowance to Keep",
        "adjustment_calc_taxable_allowance": "Taxable Allowance to Keep",
        "adjustment_calc_non_taxable_allowance": "Non-Taxable Allowance to Keep",
        "adjustment_calc_active": "Output as active employee",
        "adjustment_calc_run": "Run Batch CSV Calculation",
        "adjustment_calc_result": "Calculation Result",
        "adjustment_calc_target_step": "Target Step",
        "adjustment_calc_new_basic": "New Base Pay",
        "adjustment_calc_university_allowance": "University Allowance",
        "adjustment_calc_required_adjustment": "Required Adjustment Allowance",
        "adjustment_calc_new_total": "New Total Pay",
        "adjustment_calc_download": "Download Batch Result CSV",
        "adjustment_calc_download_excel": "Download Batch Result Excel",
        "adjustment_calc_step_logic": "Step Selection Logic",
        "adjustment_calc_adjustment_logic": "Adjustment Allowance Logic",
        "adjustment_calc_result_text": "First, the app selects the earliest step in the new grade whose base pay does not fall below the current base pay. Then, if the new total pay is still below the current total pay, the gap is added as an adjustment allowance.",
        "current_grade": "Current Grade",
        "current_step": "Current Step",
        "current_salary": "Current Salary",
        "min_required": "Minimum Required for Promotion",
        "promoted_grade": "Promoted Grade",
        "promoted_step": "Promoted Step",
        "promoted_salary": "Promoted Base Salary",
        "adjust_allowance": "Adjustment Allowance",
        "univ_allowance": "University Allowance",
        "is_univ": "University Graduate",
        "other_allowance": "Other Allowance",
        "taxable_allowance": "Taxable Allowance",
        "non_taxable_allowance": "Non-Taxable Allowance",
        "final_salary": "Final Pay",
        "simulate": "Run Simulation",
        "no_next_grade": "No higher grade is available.",
        "gs_before": "Current GS",
        "gs_after": "New GS",
        "promotion_flow": "Promotion Flow",
        "step_search_result": "Step Search Result",
        "allowance_export_heading": "Allowance-Included Wage Table",
        "allowance_export_text": "You can view and export a wage table with fixed allowances added.",
        "adjustment_allowance_export": "Adjustment allowance (fixed)",
        "university_allowance_export": "University allowance (fixed)",
        "other_allowance_export": "Other allowance (fixed)",
        "include_adjustment_allowance": "Include adjustment allowance",
        "include_university_allowance": "Include university allowance",
        "include_other_allowance": "Include other allowance",
        "export_with_allowances_csv": "Download allowance CSV",
        "export_with_allowances_excel": "Download allowance Excel",
        "employee_heading": "Employee Roster",
        "employee_text": "Import an employee roster CSV and calculate base pay, allowances, and total pay for each employee.",
        "employee_template_download": "Download employee roster template",
        "employee_upload": "Upload employee roster CSV",
        "employee_apply": "Apply employee roster",
        "employee_preview": "Employee roster preview",
        "employee_import_success": "Employee roster was applied.",
        "employee_import_empty": "Please choose an employee roster CSV.",
        "employee_import_error": "Employee roster CSV format is invalid.",
        "employee_export_csv": "Download employee payroll CSV",
        "employee_export_excel": "Download employee payroll Excel",
        "employee_id": "Employee ID",
        "employee_name": "Name",
        "employee_grade": "Grade",
        "employee_step": "Step",
        "employee_basic_pay": "Base Pay",
        "employee_university_flag": "University Graduate",
        "employee_adjustment_allowance": "Adjustment Allowance",
        "employee_other_allowance": "Other Allowance",
        "employee_taxable_allowance": "Taxable Allowance",
        "employee_non_taxable_allowance": "Non-Taxable Allowance",
        "employee_university_allowance": "University Allowance",
        "employee_total_allowance": "Allowance Total",
        "employee_total_pay": "Total Pay",
        "employee_sss": "SSS (Employee Share)",
        "employee_philhealth": "PhilHealth (Employee Share)",
        "employee_pagibig": "HDMF / Pag-IBIG (Employee Share)",
        "employee_taxable_income": "Taxable Monthly Pay",
        "employee_withholding_tax": "Withholding Tax",
        "employee_total_deductions": "Total Deductions",
        "employee_net_pay": "Net Pay",
        "employee_net_note": "Net pay here is an estimate that includes SSS, PhilHealth, HDMF/Pag-IBIG, and BIR withholding tax. It does not yet include loans, absences/tardiness, overtime, night differential, holiday pay, non-taxable benefits, 13th-month pay, or year-end tax adjustment.",
        "active_only": "Show active employees only",
        "default_university_allowance": "Fixed university allowance for roster calculation",
        "admin_heading": "Admin Settings",
        "admin_text": "Here you can change the auto-generation rule for the initial table. If actual salary values are fixed, you can edit the wage table directly below.",
        "base_salary": "Base Salary at Step 1",
        "ap": "AP (Annual Raise)",
        "pp": "PP (Promotion Raise)",
        "rebuild": "Rebuild table from settings",
        "reset": "Reset to defaults",
        "warning_rebuild": "Rebuilding will overwrite current manual edits.",
        "success_rebuild": "The wage table was rebuilt and saved.",
        "success_reset": "Defaults were restored and saved.",
        "csv_import_heading": "Settings CSV Import",
        "csv_import_text": "You can bulk update the settings shown on this screen (Base at Step 1, AP, and PP) by CSV. After import, the wage table is regenerated and saved to Supabase.",
        "csv_upload": "Upload settings CSV file",
        "csv_apply": "Apply CSV to settings",
        "csv_template_download": "Download settings CSV template",
        "csv_import_success": "The settings were updated from CSV, the wage table was regenerated, and the changes were saved.",
        "csv_import_error": "The CSV format is invalid. The file must contain Grade, Base, AP, and PP columns, with 6 rows for G6, G5B, G5A, G4, G3, and G2.",
        "csv_import_empty": "Please choose a CSV file first.",
        "csv_preview_heading": "CSV Preview",
        "currency_preview": "Preview",
        "excel_unavailable": "Excel export is unavailable in this environment. Please use CSV export or add openpyxl / xlsxwriter to requirements.txt.",
        "supabase_status_ok": "Supabase connection: ON",
        "supabase_status_off": "Supabase connection: OFF (using local defaults)",
        "supabase_save_error": "Failed to save to Supabase.",
        "admin_password": "Admin password",
        "admin_unlock": "Unlock admin",
        "admin_locked": "A password is required to change admin settings.",
        "admin_unlocked": "Admin is unlocked.",
        "admin_password_error": "Incorrect password.",
        "admin_only_upload_notice": "🔒 This action is available to administrators only. General users can view data only.",
    },
}


def t(key: str) -> str:
    return LANGUAGE_PACK[st.session_state.lang][key]


def grade_label(grade: str) -> str:
    return LANGUAGE_PACK[st.session_state.lang][f"glabel_{grade}"]

def lang_text(ja: str, en: str) -> str:
    return ja if st.session_state.lang == "日本語" else en

def area_label(area: str) -> str:
    return AREA_LABELS.get(area, {}).get(st.session_state.lang, area)

def format_money(value: float) -> str:
    decimals = st.session_state.decimals
    symbol = st.session_state.currency_symbol
    try:
        return f"{symbol}{float(value):,.{decimals}f}"
    except Exception:
        return "-"


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def login_enabled() -> bool:
    return get_supabase_config() is not None


def daily_to_monthly_base(min_wage: float) -> float:
    return round(float(min_wage) * WORK_DAYS_PER_YEAR / MONTHS_PER_YEAR, 2)

def get_grade_base_differentials(params: Dict[str, Dict[str, float]]) -> Dict[str, float]:
    g6_base = float(params["G6"]["base"])
    return {g: float(params[g]["base"]) - g6_base for g in GRADES}

def build_area_params(params: Dict[str, Dict[str, float]], area_min_wages: Dict[str, float], area: str) -> Dict[str, Dict[str, float]]:
    differentials = get_grade_base_differentials(params)
    g6_base = daily_to_monthly_base(float(area_min_wages[area]))
    out: Dict[str, Dict[str, float]] = {}
    for g in GRADES:
        out[g] = {
            "base": g6_base + differentials[g],
            "ap": float(params[g]["ap"]),
            "pp": float(params[g]["pp"]),
        }
    return out

def build_wage_table(params: Dict[str, Dict[str, float]], area_min_wages: Dict[str, float], area: str) -> pd.DataFrame:
    area_params = build_area_params(params, area_min_wages, area)
    data = {"Step": STEPS}
    for g in GRADES:
        base = area_params[g]["base"]
        ap = area_params[g]["ap"]
        data[g] = [base + (step - 1) * ap for step in STEPS]
    return pd.DataFrame(data)

def build_all_area_wage_tables(params: Dict[str, Dict[str, float]], area_min_wages: Dict[str, float]) -> Dict[str, pd.DataFrame]:
    return {area: build_wage_table(params, area_min_wages, area) for area in AREAS}


def make_excel_file(df: pd.DataFrame) -> Optional[bytes]:
    output = BytesIO()
    try:
        if OPENPYXL_AVAILABLE:
            engine = "openpyxl"
        elif XLSXWRITER_AVAILABLE:
            engine = "xlsxwriter"
        else:
            return None
        with pd.ExcelWriter(output, engine=engine) as writer:
            df.to_excel(writer, index=False, sheet_name="Export")
        output.seek(0)
        return output.getvalue()
    except Exception:
        return None


def build_settings_csv_template() -> pd.DataFrame:
    return pd.DataFrame([
        {"Grade": g, "Base": DEFAULT_PARAMS[g]["base"], "AP": DEFAULT_PARAMS[g]["ap"], "PP": DEFAULT_PARAMS[g]["pp"]}
        for g in GRADES
    ])


def build_employee_csv_template() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "Employee ID": "E001",
            "Name": "Sample Employee",
            "Area": "Davao",
            "Grade": "G5A",
            "Step": 4,
            "University Graduate": 1,
            "Adjustment Allowance": 1000,
            "Taxable Allowance": 500,
            "Non-Taxable Allowance": 200,
            "Active": 1,
        }
    ])


def build_adjustment_batch_csv_template() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "Employee ID": "E001",
            "Name": "Sample Employee",
            "Area": "Davao",
            "New Grade": "G4",
            "Current Basic Pay": 20000,
            "Current Total Pay": 22000,
            "University Graduate": 1,
            "Taxable Allowance": 0,
            "Non-Taxable Allowance": 0,
            "Active": 1,
        }
    ])


def validate_adjustment_batch_csv(df: pd.DataFrame) -> pd.DataFrame:
    required_cols = [
        "Employee ID",
        "Name",
        "Area",
        "New Grade",
        "Current Basic Pay",
        "Current Total Pay",
        "University Graduate",
        "Taxable Allowance",
        "Non-Taxable Allowance",
        "Active",
    ]
    if list(df.columns) != required_cols:
        raise ValueError(f"Columns must be exactly: {required_cols}")

    out = df.copy()
    out["Area"] = out["Area"].astype(str)
    if not out["Area"].isin(AREAS).all():
        raise ValueError(f"Area column contains invalid area. Allowed: {AREAS}")

    out["New Grade"] = out["New Grade"].astype(str)
    if not out["New Grade"].isin(GRADES).all():
        raise ValueError(f"New Grade column contains invalid grade. Allowed: {GRADES}")

    for col in ["Current Basic Pay", "Current Total Pay", "University Graduate", "Taxable Allowance", "Non-Taxable Allowance", "Active"]:
        out[col] = pd.to_numeric(out[col], errors="raise")

    out["University Graduate"] = out["University Graduate"].astype(int)
    out["Active"] = out["Active"].astype(int)
    return out


def build_adjustment_batch_upload_df(
    source_df: pd.DataFrame,
    area_wage_tables: Dict[str, pd.DataFrame],
    university_allowance_amount: float,
) -> pd.DataFrame:
    rows = []
    for _, row in source_df.iterrows():
        result = calculate_adjustment_allowance_result(
            area=str(row["Area"]),
            target_grade=str(row["New Grade"]),
            current_basic_pay=float(row["Current Basic Pay"]),
            current_total_pay=float(row["Current Total Pay"]),
            is_university_graduate=int(row["University Graduate"]) == 1,
            taxable_allowance=float(row["Taxable Allowance"]),
            non_taxable_allowance=float(row["Non-Taxable Allowance"]),
            area_wage_tables=area_wage_tables,
            university_allowance_amount=university_allowance_amount,
        )
        rows.append({
            "Employee ID": str(row["Employee ID"]),
            "Name": str(row["Name"]),
            "Area": result["area"],
            "Grade": result["target_grade"],
            "Step": int(result["target_step"]),
            "University Graduate": int(result["is_university_graduate"]),
            "Adjustment Allowance": float(result["adjustment_allowance"]),
            "Taxable Allowance": float(result["taxable_allowance"]),
            "Non-Taxable Allowance": float(result["non_taxable_allowance"]),
            "Active": int(row["Active"]),
        })
    return pd.DataFrame(rows)


def validate_imported_settings_csv(df: pd.DataFrame) -> Dict[str, Dict[str, float]]:
    required_cols = ["Grade", "Base", "AP", "PP"]
    if list(df.columns) != required_cols:
        raise ValueError(f"Columns must be exactly: {required_cols}")
    if len(df) != len(GRADES):
        raise ValueError(f"Row count must be {len(GRADES)}")
    if df["Grade"].tolist() != GRADES:
        raise ValueError(f"Grade order must be: {GRADES}")

    new_params: Dict[str, Dict[str, float]] = {}
    for i, row in df.iterrows():
        try:
            new_params[str(row["Grade"])] = {
                "base": float(row["Base"]),
                "ap": float(row["AP"]),
                "pp": float(row["PP"]),
            }
        except Exception as exc:
            raise ValueError(f"Row {i + 1}: Base/AP/PP must be numeric") from exc
    return new_params


def validate_employee_roster_csv(df: pd.DataFrame) -> pd.DataFrame:
    required_cols = DEFAULT_EMPLOYEE_COLUMNS
    legacy_cols = [
        "Employee ID",
        "Name",
        "Area",
        "Grade",
        "Step",
        "University Graduate",
        "Adjustment Allowance",
        "Other Allowance",
        "Active",
    ]
    if list(df.columns) == legacy_cols:
        out = df.copy().rename(columns={"Other Allowance": "Taxable Allowance"})
        out["Non-Taxable Allowance"] = 0.0
        out = out[required_cols]
    elif list(df.columns) == required_cols:
        out = df.copy()
    else:
        raise ValueError(f"Columns must be exactly: {required_cols}")

    out["Area"] = out["Area"].astype(str).str.strip()
    if not out["Area"].isin(AREAS).all():
        raise ValueError(f"Area column contains invalid area. Allowed: {AREAS}")

    out["Grade"] = out["Grade"].astype(str)
    if not out["Grade"].isin(GRADES).all():
        raise ValueError("Grade column contains invalid grade")

    out["Step"] = pd.to_numeric(out["Step"], errors="raise").astype(int)
    if not out["Step"].isin(STEPS).all():
        raise ValueError("Step column contains invalid step")

    for col in ["University Graduate", "Adjustment Allowance", "Taxable Allowance", "Non-Taxable Allowance", "Active"]:
        out[col] = pd.to_numeric(out[col], errors="raise")

    out["University Graduate"] = out["University Graduate"].astype(int)
    out["Active"] = out["Active"].astype(int)
    return out


def params_to_rows(params: Dict[str, Dict[str, float]]) -> List[Dict[str, float]]:
    return [
        {"grade": g, "base": float(params[g]["base"]), "ap": float(params[g]["ap"]), "pp": float(params[g]["pp"])}
        for g in GRADES
    ]


def rows_to_params(rows: List[Dict[str, float]]) -> Dict[str, Dict[str, float]]:
    rows_by_grade = {row["grade"]: row for row in rows}
    params: Dict[str, Dict[str, float]] = {}
    for g in GRADES:
        params[g] = {
            "base": float(rows_by_grade[g]["base"]),
            "ap": float(rows_by_grade[g]["ap"]),
            "pp": float(rows_by_grade[g]["pp"]),
        }
    return params


def get_supabase_config() -> Optional[Dict[str, str]]:
    try:
        url = st.secrets["SUPABASE_URL"]
        service_role_key = (
            st.secrets.get("SUPABASE_SERVICE_ROLE_KEY")
            or st.secrets.get("SUPABASE_KEY")
            or st.secrets.get("SUPABASE_ANON_KEY")
        )
        if not service_role_key:
            return None
        table = st.secrets.get("SUPABASE_TABLE", "wage_settings")
        users_table = st.secrets.get("SUPABASE_USERS_TABLE", "app_users")
        return {
            "url": str(url).rstrip("/"),
            "key": str(service_role_key),
            "table": str(table),
            "users_table": str(users_table),
        }
    except Exception:
        return None


def supabase_request(method: str, path: str, body: Optional[object] = None, query: Optional[Dict[str, str]] = None):
    config = get_supabase_config()
    if config is None:
        raise RuntimeError("Supabase is not configured")

    url = f"{config['url']}/rest/v1/{path}"
    if query:
        url = f"{url}?{parse.urlencode(query)}"

    headers = {
        "apikey": config["key"],
        "Authorization": f"Bearer {config['key']}",
        "Content-Type": "application/json",
    }
    if method == "POST":
        headers["Prefer"] = "resolution=merge-duplicates,return=representation"
    elif method in ("PATCH",):
        headers["Prefer"] = "return=representation"

    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")

    req = request.Request(url=url, data=data, headers=headers, method=method)
    with request.urlopen(req, timeout=20) as response:
        text = response.read().decode("utf-8")
        return json.loads(text) if text else None


def load_settings_from_supabase() -> Dict[str, Dict[str, float]]:
    config = get_supabase_config()
    if config is None:
        return {k: v.copy() for k, v in DEFAULT_PARAMS.items()}
    try:
        result = supabase_request(
            method="GET",
            path=config["table"],
            query={"select": "grade,base,ap,pp", "order": "grade.asc"},
        )
        if not result:
            return {k: v.copy() for k, v in DEFAULT_PARAMS.items()}
        grades_found = [row["grade"] for row in result]
        if sorted(grades_found) != sorted(GRADES):
            return {k: v.copy() for k, v in DEFAULT_PARAMS.items()}
        return rows_to_params(result)
    except Exception:
        return {k: v.copy() for k, v in DEFAULT_PARAMS.items()}


def save_settings_to_supabase(params: Dict[str, Dict[str, float]]) -> None:
    config = get_supabase_config()
    if config is None:
        return
    try:
        supabase_request(method="POST", path=config["table"], body=params_to_rows(params), query={"on_conflict": "grade"})
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(detail) from exc
    except Exception as exc:
        raise RuntimeError(str(exc)) from exc


def load_area_min_wages_from_supabase() -> Dict[str, float]:
    config = get_supabase_config()
    if config is None:
        return DEFAULT_AREA_MIN_WAGES.copy()
    table = "area_min_wages"
    try:
        result = supabase_request(
            method="GET",
            path=table,
            query={"select": "area,min_wage", "order": "area.asc"},
        )
        if not result:
            return DEFAULT_AREA_MIN_WAGES.copy()
        out = DEFAULT_AREA_MIN_WAGES.copy()
        for row in result:
            area = str(row.get("area", "")).strip()
            if area in out:
                out[area] = float(row.get("min_wage", out[area]))
        return out
    except Exception:
        return DEFAULT_AREA_MIN_WAGES.copy()

def save_area_min_wages_to_supabase(area_min_wages: Dict[str, float]) -> None:
    config = get_supabase_config()
    if config is None:
        return
    table = "area_min_wages"
    body = [{"area": area, "min_wage": float(area_min_wages[area])} for area in AREAS]
    try:
        supabase_request(method="POST", path=table, body=body, query={"on_conflict": "area"})
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(detail) from exc
    except Exception as exc:
        raise RuntimeError(str(exc)) from exc

def get_login_users_from_supabase() -> List[Dict[str, object]]:


    config = get_supabase_config()
    if config is None:
        return []
    try:
        result = supabase_request(
            method="GET",
            path=config["users_table"],
            query={"select": "*", "limit": "500"},
        )
        if isinstance(result, list):
            return result if isinstance(result, list) else []
        return []
        
    except Exception:
        return []


def _candidate_login_values(user: Dict[str, object]) -> List[str]:
    keys = ["username", "login_id", "user_id", "email", "id"]
    values: List[str] = []
    for key in keys:
        value = user.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            values.append(text)
    return values


def get_user_by_login_id(login_id: str) -> Optional[Dict[str, object]]:
    users = get_login_users_from_supabase()
    for user in users:
        if str(user.get("username")).strip() == login_id:
            return user
    return None


def verify_password(password: str, user: Dict[str, object]) -> bool:
    raw = str(password or "")
    stored = str(user.get("password_hash") or "").strip()

    if not stored:
        return False

    input_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()

    return stored.lower() == input_hash.lower()


def normalize_role(role_value: object) -> str:
    role = str(role_value or "viewer").strip().lower()
    return role if role in ("admin", "viewer") else "viewer"


def is_user_active(user: Dict[str, object]) -> bool:
    value = user.get("is_active", True)
    if value is None:
        return True
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("true", "1", "yes", "y")


def authenticate_user(login_id: str, password: str) -> Optional[Dict[str, object]]:
    user = get_user_by_login_id(login_id)
    if not user:
        return None
    if not is_user_active(user):
        return None
    if not verify_password(password, user):
        return None
    user["role"] = normalize_role(user.get("role"))
    return user


def is_admin() -> bool:
    return st.session_state.get("user_role", "viewer") == "admin"


def is_viewer() -> bool:
    return st.session_state.get("user_role", "viewer") in ("viewer", "admin")


def get_current_salary(df: pd.DataFrame, grade: str, step: int) -> float:
    row = df.loc[df["Step"] == step]
    return float(row.iloc[0][grade])


def find_promotion_result(df: pd.DataFrame, params: Dict[str, Dict[str, float]], current_grade: str, current_step: int) -> Optional[Dict[str, float]]:
    next_grade = NEXT_GRADE[current_grade]
    if not next_grade:
        return None
    current_salary = get_current_salary(df, current_grade, current_step)
    minimum_required = current_salary + params[current_grade]["ap"] + params[current_grade]["pp"]
    next_rows = df[["Step", next_grade]].copy()
    eligible = next_rows[next_rows[next_grade] >= minimum_required]
    if eligible.empty:
        target_step = int(next_rows.iloc[-1]["Step"])
        target_salary = float(next_rows.iloc[-1][next_grade])
    else:
        target_step = int(eligible.iloc[0]["Step"])
        target_salary = float(eligible.iloc[0][next_grade])
    return {
        "current_salary": current_salary,
        "minimum_required": minimum_required,
        "target_step": target_step,
        "target_salary": target_salary,
        "target_grade": next_grade,
    }


def find_step_for_minimum_base(wage_df: pd.DataFrame, grade: str, minimum_base: float) -> Dict[str, float]:
    next_rows = wage_df[["Step", grade]].copy()
    eligible = next_rows[next_rows[grade] >= float(minimum_base)]
    if eligible.empty:
        target_step = int(next_rows.iloc[-1]["Step"])
        target_salary = float(next_rows.iloc[-1][grade])
    else:
        target_step = int(eligible.iloc[0]["Step"])
        target_salary = float(eligible.iloc[0][grade])
    return {
        "target_step": target_step,
        "target_salary": target_salary,
    }


def calculate_adjustment_allowance_result(
    area: str,
    target_grade: str,
    current_basic_pay: float,
    current_total_pay: float,
    is_university_graduate: bool,
    taxable_allowance: float,
    non_taxable_allowance: float,
    area_wage_tables: Dict[str, pd.DataFrame],
    university_allowance_amount: float,
) -> Dict[str, float]:
    wage_df = area_wage_tables[area]
    step_result = find_step_for_minimum_base(wage_df, target_grade, current_basic_pay)
    target_step = int(step_result["target_step"])
    new_basic_pay = float(step_result["target_salary"])
    university_allowance = float(university_allowance_amount if is_university_graduate else 0.0)
    subtotal_before_adjustment = new_basic_pay + float(taxable_allowance) + float(non_taxable_allowance) + university_allowance
    adjustment_allowance = max(float(current_total_pay) - subtotal_before_adjustment, 0.0)
    new_total_pay = subtotal_before_adjustment + adjustment_allowance
    return {
        "area": area,
        "target_grade": target_grade,
        "target_step": target_step,
        "current_basic_pay": float(current_basic_pay),
        "current_total_pay": float(current_total_pay),
        "new_basic_pay": new_basic_pay,
        "taxable_allowance": float(taxable_allowance),
        "non_taxable_allowance": float(non_taxable_allowance),
        "university_allowance": university_allowance,
        "adjustment_allowance": adjustment_allowance,
        "new_total_pay": new_total_pay,
        "is_university_graduate": int(1 if is_university_graduate else 0),
    }


def build_adjustment_upload_row(
    employee_id: str,
    name: str,
    result: Dict[str, float],
    active: bool = True,
) -> pd.DataFrame:
    return pd.DataFrame([{
        "Employee ID": employee_id,
        "Name": name,
        "Area": result["area"],
        "Grade": result["target_grade"],
        "Step": int(result["target_step"]),
        "University Graduate": int(result["is_university_graduate"]),
        "Adjustment Allowance": float(result["adjustment_allowance"]),
        "Taxable Allowance": float(result["taxable_allowance"]),
        "Non-Taxable Allowance": float(result["non_taxable_allowance"]),
        "Active": int(1 if active else 0),
    }])


def build_allowance_export_table(df: pd.DataFrame, include_adjustment: bool, adjustment_amount: float, include_university: bool, university_amount: float, include_other: bool, other_amount: float) -> pd.DataFrame:
    out = df.copy()
    allowance_total = 0.0
    if include_adjustment:
        allowance_total += adjustment_amount
    if include_university:
        allowance_total += university_amount
    if include_other:
        allowance_total += other_amount
    for g in GRADES:
        out[g] = pd.to_numeric(out[g], errors="coerce")
    out["Allowance Total"] = allowance_total
    for g in GRADES:
        out[f"{g} Total"] = out[g] + allowance_total
    return out


def get_sss_monthly_salary_credit(monthly_compensation: float) -> float:
    comp = max(float(monthly_compensation or 0.0), 0.0)
    if comp < 5250:
        return 5000.0
    if comp >= 34750:
        return 35000.0
    steps = int((comp - 5250) // 500)
    return 5500.0 + (steps * 500.0)


def compute_sss_employee_share(monthly_compensation: float) -> float:
    msc = get_sss_monthly_salary_credit(monthly_compensation)
    regular_ss = msc * 0.05
    mpf = max(msc - 20000.0, 0.0) * 0.025
    return round(regular_ss + mpf, 2)


def compute_philhealth_employee_share(monthly_basic_salary: float) -> float:
    mbs = min(max(float(monthly_basic_salary or 0.0), 10000.0), 100000.0)
    monthly_premium = round(mbs * 0.05, 2)
    return round(monthly_premium / 2.0, 2)


def compute_pagibig_employee_share(monthly_compensation: float) -> float:
    comp = max(float(monthly_compensation or 0.0), 0.0)
    fund_salary = min(comp, 10000.0)
    rate = 0.01 if comp <= 1500.0 else 0.02
    return round(fund_salary * rate, 2)


def compute_monthly_withholding_tax(taxable_monthly_pay: float) -> float:
    pay = max(float(taxable_monthly_pay or 0.0), 0.0)
    if pay <= 20833:
        tax = 0.0
    elif pay <= 33332:
        tax = (pay - 20833.0) * 0.15
    elif pay <= 66666:
        tax = 1875.0 + (pay - 33333.0) * 0.20
    elif pay <= 166666:
        tax = 8541.80 + (pay - 66667.0) * 0.25
    elif pay <= 666666:
        tax = 33541.80 + (pay - 166667.0) * 0.30
    else:
        tax = 183541.80 + (pay - 666667.0) * 0.35
    return round(max(tax, 0.0), 2)


def compute_employee_net_pay_components(
    basic_pay: float,
    taxable_pay: float,
    gross_pay: float,
) -> Dict[str, float]:
    contributory_compensation = max(float(taxable_pay or 0.0), 0.0)
    sss_employee = compute_sss_employee_share(contributory_compensation)
    philhealth_employee = compute_philhealth_employee_share(basic_pay)
    pagibig_employee = compute_pagibig_employee_share(contributory_compensation)
    taxable_monthly_pay = max(contributory_compensation - sss_employee - philhealth_employee - pagibig_employee, 0.0)
    withholding_tax = compute_monthly_withholding_tax(taxable_monthly_pay)
    total_deductions = round(sss_employee + philhealth_employee + pagibig_employee + withholding_tax, 2)
    net_pay = round(gross_pay - total_deductions, 2)
    return {
        "sss_employee": round(sss_employee, 2),
        "philhealth_employee": round(philhealth_employee, 2),
        "pagibig_employee": round(pagibig_employee, 2),
        "taxable_monthly_pay": round(taxable_monthly_pay, 2),
        "withholding_tax": round(withholding_tax, 2),
        "total_deductions": round(total_deductions, 2),
        "net_pay": round(net_pay, 2),
    }


def build_employee_payroll(
    roster_df: pd.DataFrame,
    area_wage_tables: Dict[str, pd.DataFrame],
    university_allowance_amount: float,
) -> pd.DataFrame:
    rows = []
    for _, row in roster_df.iterrows():
        area = str(row["Area"]).strip()
        wage_df = area_wage_tables[area]
        grade = str(row["Grade"])
        step = int(row["Step"])
        basic_pay = get_current_salary(wage_df, grade, step)
        adjustment_allowance = float(row["Adjustment Allowance"])
        taxable_allowance = float(row["Taxable Allowance"])
        non_taxable_allowance = float(row["Non-Taxable Allowance"])
        university_flag = int(row["University Graduate"])
        university_allowance = float(university_allowance_amount if university_flag == 1 else 0.0)
        total_allowance = adjustment_allowance + taxable_allowance + non_taxable_allowance + university_allowance
        taxable_pay = basic_pay + adjustment_allowance + taxable_allowance + university_allowance
        total_pay = basic_pay + total_allowance
        net_components = compute_employee_net_pay_components(basic_pay=basic_pay, taxable_pay=taxable_pay, gross_pay=total_pay)
        rows.append({
            t("employee_id"): str(row["Employee ID"]),
            t("employee_name"): str(row["Name"]),
            lang_text("エリア", "Area"): area_label(area),
            t("employee_grade"): grade,
            t("employee_step"): step,
            t("employee_basic_pay"): basic_pay,
            t("employee_university_flag"): university_flag,
            t("employee_adjustment_allowance"): adjustment_allowance,
            t("employee_taxable_allowance"): taxable_allowance,
            t("employee_non_taxable_allowance"): non_taxable_allowance,
            t("employee_university_allowance"): university_allowance,
            t("employee_total_allowance"): total_allowance,
            t("employee_total_pay"): total_pay,
            t("employee_sss"): net_components["sss_employee"],
            t("employee_philhealth"): net_components["philhealth_employee"],
            t("employee_pagibig"): net_components["pagibig_employee"],
            t("employee_taxable_income"): net_components["taxable_monthly_pay"],
            t("employee_withholding_tax"): net_components["withholding_tax"],
            t("employee_total_deductions"): net_components["total_deductions"],
            t("employee_net_pay"): net_components["net_pay"],
            "_active": int(row["Active"]),
        })
    return pd.DataFrame(rows)

def display_table_with_formats(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for g in GRADES:
        out[g] = out[g].apply(format_money)
    return out


def display_table_with_gs(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in df.iterrows():
        step = int(row["Step"])
        record = {"Step": step}
        for g in GRADES:
            record[g] = f"{g}-S{step} / {format_money(float(row[g]))}"
        rows.append(record)
    return pd.DataFrame(rows)

def current_area_wage_df() -> pd.DataFrame:
    return build_wage_table(
        st.session_state.params,
        st.session_state.area_min_wages,
        st.session_state.selected_area,
    )

def current_area_params() -> Dict[str, Dict[str, float]]:
    return build_area_params(
        st.session_state.params,
        st.session_state.area_min_wages,
        st.session_state.selected_area,
    )

def all_area_wage_tables() -> Dict[str, pd.DataFrame]:
    return build_all_area_wage_tables(st.session_state.params, st.session_state.area_min_wages)

def build_area_min_wage_table(area_min_wages: Dict[str, float]) -> pd.DataFrame:
    return pd.DataFrame([
        {
            lang_text("エリア", "Area"): area_label(area),
            "AreaKey": area,
            lang_text("最低日給", "Daily Minimum Wage"): float(area_min_wages[area]),
            lang_text("G6 Step1 月給", "G6 Step1 Monthly Base"): daily_to_monthly_base(area_min_wages[area]),
        }
        for area in AREAS
    ])

def grade_step_grid(selected_grade: str = "G5A", selected_step: int = 4) -> str:
    lines = []
    lines.append("digraph G {")
    lines.append("rankdir=TB;")
    lines.append('graph [nodesep="0.25", ranksep="0.35"];')
    lines.append('node [shape="box", style="rounded,filled", fillcolor="white", width="1.0", height="0.5", fontsize="10"];')
    headers = []
    for g in GRADES:
        header = f"header_{g}"
        lines.append(f'{header} [label="{g}", shape="plaintext", fontsize="12"];')
        headers.append(header)
    lines.append("{ rank=same; " + "; ".join(headers) + "; }")
    for s in range(1, 6):
        row_nodes = []
        for g in GRADES:
            node_name = f"{g}_{s}"
            label = f"{g}-S{s}"
            if g == selected_grade and s == selected_step:
                lines.append(f'{node_name} [label="{label}", fillcolor="lightblue"];')
            else:
                lines.append(f'{node_name} [label="{label}"];')
            row_nodes.append(node_name)
        lines.append("{ rank=same; " + "; ".join(row_nodes) + "; }")
    for g in GRADES:
        chain = [f"header_{g}"] + [f"{g}_{s}" for s in range(1, 6)]
        for i in range(len(chain) - 1):
            lines.append(f'{chain[i]} -> {chain[i + 1]} [style="invis", weight=10];')
    lines.append("}")
    return "\n".join(lines)


def raise_diagram() -> str:
    return """
    digraph G {
      rankdir=LR;
      node [shape="box", style="rounded,filled", fillcolor="white"];
      A [label="Current Salary\n現在給与"];
      B [label="+ AP\nAnnual Raise"];
      C [label="+ PP\nPromotion Raise"];
      D [label="Minimum Required\n最低必要額"];
      E [label="Find first Step in next Grade\n次グレードで該当Stepを探す", fillcolor="lightyellow"];
      A -> B -> C -> D -> E;
    }
    """


def promotion_diagram(current_grade: str, current_step: int, next_grade: str, target_step: int) -> str:
    return f"""
    digraph G {{
      rankdir=LR;
      node [shape="box", style="rounded,filled", fillcolor="white"];
      A [label="{current_grade}-S{current_step}\nCurrent GS", fillcolor="lightblue"];
      B [label="AP + PP\nadded"];
      C [label="Search next grade\n{next_grade}"];
      D [label="{next_grade}-S{target_step}\nNew GS", fillcolor="lightgreen"];
      A -> B -> C -> D;
    }}
    """


def save_and_rebuild(
    params: Optional[Dict[str, Dict[str, float]]] = None,
    area_min_wages: Optional[Dict[str, float]] = None,
) -> None:
    if params is not None:
        st.session_state.params = params
        save_settings_to_supabase(params)
    if area_min_wages is not None:
        st.session_state.area_min_wages = area_min_wages
        save_area_min_wages_to_supabase(area_min_wages)


# =========================================================
# Session state
# =========================================================
if "lang" not in st.session_state:
    st.session_state.lang = "日本語"
if "currency_symbol" not in st.session_state:
    st.session_state.currency_symbol = "₱"
if "decimals" not in st.session_state:
    st.session_state.decimals = 0
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "login_user" not in st.session_state:
    st.session_state.login_user = ""
if "display_name" not in st.session_state:
    st.session_state.display_name = ""
if "user_role" not in st.session_state:
    st.session_state.user_role = "viewer"
if "params" not in st.session_state:
    st.session_state.params = load_settings_from_supabase()
if "area_min_wages" not in st.session_state:
    st.session_state.area_min_wages = load_area_min_wages_from_supabase()
if "selected_area" not in st.session_state:
    st.session_state.selected_area = "Davao"
if "employee_roster_df" not in st.session_state:
    st.session_state.employee_roster_df = pd.DataFrame(columns=DEFAULT_EMPLOYEE_COLUMNS)
if "adjustment_upload_df" not in st.session_state:
    st.session_state.adjustment_upload_df = pd.DataFrame(columns=DEFAULT_EMPLOYEE_COLUMNS)

# =========================================================
# Simple visual styling
# =========================================================
st.markdown(
    """
    <style>
    .main-card {
        background: linear-gradient(135deg, #f8fbff 0%, #eef6ff 100%);
        border: 1px solid #d7e7ff;
        border-radius: 14px;
        padding: 14px 16px;
        margin-bottom: 14px;
    }
    .info-card {
        background: #f7fafc;
        border-left: 5px solid #4a90e2;
        border-radius: 10px;
        padding: 12px 14px;
        margin-bottom: 12px;
    }
    .warn-card {
        background: #fff8e8;
        border-left: 5px solid #f0ad4e;
        border-radius: 10px;
        padding: 12px 14px;
        margin-bottom: 12px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# =========================================================
# Login gate
# =========================================================
if login_enabled() and not st.session_state.logged_in:
    st.title(t("login_title"))
    login_id = st.text_input(t("login_id"))
    login_password = st.text_input(t("login_password"), type="password")
    if st.button(t("login_button"), use_container_width=True):
        user = authenticate_user(login_id.strip(), login_password)
        if user is not None:
            resolved_login = ""
            for k in ("username", "login_id", "user_id", "email", "id"):
                v = str(user.get(k) or "").strip()
                if v:
                    resolved_login = v
                    break
            st.session_state.logged_in = True
            st.session_state.login_user = resolved_login or login_id.strip()
            st.session_state.display_name = str(user.get("display_name") or st.session_state.login_user).strip()
            st.session_state.user_role = normalize_role(user.get("role"))
            st.rerun()
        else:
            st.error(t("login_error"))
            with st.expander("Login debug"):
                cfg = get_supabase_config()
                st.write({
                    "supabase_configured": cfg is not None,
                    "users_table": cfg.get("users_table") if cfg else None,
                    "user_count_preview": len(get_login_users_from_supabase()) if cfg else 0,
                    "login_id_entered": login_id.strip(),
                })
    st.stop()
elif not login_enabled():
    st.warning("Supabase login is not configured. The app is running in local viewer mode.")

if not is_admin():
    st.session_state.employee_roster_df = pd.DataFrame(columns=DEFAULT_EMPLOYEE_COLUMNS)

# =========================================================
# Sidebar
# =========================================================
st.sidebar.title("Wage Table")
st.session_state.lang = st.sidebar.radio(
    "Language / 言語",
    ["日本語", "English"],
    index=0 if st.session_state.lang == "日本語" else 1,
)
st.session_state.currency_symbol = st.sidebar.text_input(t("sidebar_currency"), value=st.session_state.currency_symbol)
st.session_state.decimals = st.sidebar.selectbox(t("sidebar_decimals"), [0, 1, 2], index=[0, 1, 2].index(st.session_state.decimals))
st.session_state.selected_area = st.sidebar.selectbox(
    lang_text("表示エリア", "Selected Area"),
    AREAS,
    index=AREAS.index(st.session_state.selected_area) if st.session_state.selected_area in AREAS else 0,
    format_func=area_label,
)

if login_enabled() and st.session_state.logged_in:
    role_label = st.session_state.user_role or "viewer"
    display_user = st.session_state.display_name or st.session_state.login_user
    st.sidebar.caption(f"{t('logged_in_as')}: {display_user} ({role_label})")
    if st.sidebar.button(t("logout_button"), use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.login_user = ""
        st.session_state.display_name = ""
        st.session_state.user_role = "viewer"
        st.session_state.employee_roster_df = pd.DataFrame(columns=DEFAULT_EMPLOYEE_COLUMNS)
        st.rerun()

if get_supabase_config() is not None:
    st.sidebar.success(t("supabase_status_ok"))
else:
    st.sidebar.info(t("supabase_status_off"))

selected_daily = st.session_state.area_min_wages.get(st.session_state.selected_area, 0.0)
st.sidebar.caption(f"{lang_text('選択エリア最低日給', 'Selected area daily minimum wage')}: {format_money(selected_daily)}")
st.sidebar.caption(f"{lang_text('G6-S1 月給', 'G6-S1 monthly base')}: {format_money(daily_to_monthly_base(selected_daily))}")
st.sidebar.caption(f"{t('currency_preview')}: {format_money(12345.67)}")
st.sidebar.markdown("---")
st.sidebar.write(t("sidebar_example"))
example_grade = st.sidebar.selectbox("Grade", GRADES, index=2, key="example_grade")
example_step = st.sidebar.selectbox("Step", STEPS, index=3, key="example_step")
st.sidebar.info(f"{lang_text('エリア', 'Area')} = {area_label(st.session_state.selected_area)} / GS = {example_grade}-S{example_step}")

# =========================================================
# Main header
# =========================================================
st.markdown(f"<div class='main-card'><h1 style='margin-bottom:4px;'>{t('title')}</h1><div>{t('subtitle')}</div></div>", unsafe_allow_html=True)

m1, m2, m3 = st.columns(3)
with m1:
    st.metric("Grades", len(GRADES))
with m2:
    st.metric("Steps", len(STEPS))
with m3:
    st.metric(lang_text("エリア数", "Areas"), len(AREAS))

tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
    t("tab_overview"),
    t("tab_diagram"),
    t("tab_table"),
    t("tab_sim"),
    t("tab_adjustment_calc"),
    t("tab_allowance_export"),
    t("tab_employee"),
    t("tab_admin"),
])

# =========================================================
# Tab 1: Overview
# =========================================================
with tab1:
    st.subheader(t("overview_heading"))
    st.write(t("overview_text1"))
    st.write(t("overview_text2"))
    st.write(t("grade_axis"))
    st.info(lang_text(
        "各エリアの G6-S1 は『最低日給 × 313日 ÷ 12か月』で自動計算します。AP と PP は全エリア共通です。",
        "For each area, G6-S1 is calculated automatically as Daily Minimum Wage × 313 days ÷ 12 months. AP and PP are shared across all areas.",
    ))

    area_summary_df = build_area_min_wage_table(st.session_state.area_min_wages).drop(columns=["AreaKey"])
    display_area_summary_df = area_summary_df.copy()
    for col in display_area_summary_df.columns[1:]:
        display_area_summary_df[col] = display_area_summary_df[col].apply(format_money)
    st.subheader(lang_text("エリア別最低賃金一覧", "Area Minimum Wage Summary"))
    st.dataframe(display_area_summary_df, use_container_width=True, hide_index=True)

    ref_df = pd.DataFrame({
        t("grade"): GRADES,
        t("position"): [grade_label(g) for g in GRADES],
        t("next_grade"): [NEXT_GRADE[g] if NEXT_GRADE[g] else "-" for g in GRADES],
    })
    st.subheader(t("grade_table"))
    st.dataframe(ref_df, use_container_width=True, hide_index=True)

    st.subheader(t("ap_pp_heading"))
    ap_pp_df = pd.DataFrame([
        {
            t("grade"): g,
            t("ap_label"): format_money(st.session_state.params[g]["ap"]),
            t("pp_label"): format_money(st.session_state.params[g]["pp"]),
        }
        for g in GRADES
    ])
    st.dataframe(ap_pp_df, use_container_width=True, hide_index=True)

# =========================================================
# Tab 2: Diagrams
# =========================================================
with tab2:
    st.subheader(t("diagram_heading1"))
    st.write(t("diagram_help1"))
    st.graphviz_chart(grade_step_grid(example_grade, min(example_step, 5)))

    st.subheader(t("diagram_heading2"))
    st.write(t("diagram_help2"))
    st.graphviz_chart(raise_diagram())

    st.subheader(t("diagram_heading3"))
    st.write(t("diagram_help3"))
    sample_df = current_area_wage_df()
    sample_params = current_area_params()
    sample_result = find_promotion_result(sample_df, sample_params, "G5A", 4)
    if sample_result:
        st.graphviz_chart(promotion_diagram("G5A", 4, sample_result["target_grade"], int(sample_result["target_step"])))
    st.info(f"{lang_text('現在の表示エリア', 'Current selected area')}: {area_label(st.session_state.selected_area)}")

# =========================================================
# Tab 3: Wage table
# =========================================================
with tab3:
    st.subheader(t("wage_heading"))
    st.caption(f"{t('wage_caption')} / {lang_text('表示エリア', 'Area')}: {area_label(st.session_state.selected_area)}")
    current_df = current_area_wage_df()
    view_mode = st.radio(t("table_view_mode"), [t("table_mode_raw"), t("table_mode_with_label")], horizontal=True)
    if view_mode == t("table_mode_raw"):
        st.dataframe(display_table_with_formats(current_df), use_container_width=True, hide_index=True)
    else:
        st.dataframe(display_table_with_gs(current_df), use_container_width=True, hide_index=True)

    csv_bytes = current_df.to_csv(index=False).encode("utf-8-sig")
    excel_bytes = make_excel_file(current_df)
    d1, d2 = st.columns(2)
    with d1:
        st.download_button(
            t("download_csv"),
            data=csv_bytes,
            file_name=f"wage_table_{st.session_state.selected_area.lower().replace(' ', '_')}.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with d2:
        if excel_bytes is not None:
            st.download_button(
                t("download_excel"),
                data=excel_bytes,
                file_name=f"wage_table_{st.session_state.selected_area.lower().replace(' ', '_')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        else:
            st.info(t("excel_unavailable"))
    st.caption(t("download_note"))

# =========================================================
# Tab 4: Promotion simulation
# =========================================================
with tab4:
    st.subheader(t("sim_heading"))
    st.caption(f"{lang_text('計算対象エリア', 'Area used for calculation')}: {area_label(st.session_state.selected_area)}")
    current_df = current_area_wage_df()
    current_params = current_area_params()
    c1, c2, c3 = st.columns(3)
    with c1:
        current_grade = st.selectbox(t("current_grade"), GRADES[:-1], index=0)
    with c2:
        current_step = st.selectbox(t("current_step"), STEPS, index=0)
    with c3:
        is_univ = st.checkbox(t("is_univ"), value=False)
    a1, a2, a3 = st.columns(3)
    with a1:
        adjustment_allowance = st.number_input(t("adjust_allowance"), min_value=0.0, value=0.0, step=100.0)
    with a2:
        university_allowance = st.number_input(t("univ_allowance"), min_value=0.0, value=0.0, step=100.0)
    with a3:
        other_allowance = st.number_input(t("other_allowance"), min_value=0.0, value=0.0, step=100.0)
    if st.button(t("simulate"), use_container_width=True, key="simulate_current"):
        result = find_promotion_result(current_df, current_params, current_grade, int(current_step))
        if result is None:
            st.warning(t("no_next_grade"))
        else:
            ap_amount = float(current_params[current_grade]["ap"])
            pp_amount = float(current_params[current_grade]["pp"])
            current_salary = float(result["current_salary"])
            minimum_required = float(result["minimum_required"])
            target_grade = str(result["target_grade"])
            target_step = int(result["target_step"])
            target_salary = float(result["target_salary"])
            total_allowance = adjustment_allowance + other_allowance + (university_allowance if is_univ else 0.0)
            final_salary = target_salary + total_allowance

            r1, r2, r3 = st.columns(3)
            with r1:
                st.metric(t("gs_before"), f"{current_grade}-S{current_step}")
            with r2:
                st.metric(t("gs_after"), f"{target_grade}-S{target_step}")
            with r3:
                st.metric(t("final_salary"), format_money(final_salary))

            st.subheader(t("promotion_flow"))
            st.graphviz_chart(promotion_diagram(current_grade, int(current_step), target_grade, target_step))

            st.subheader(t("sim_explanation_heading"))
            if st.session_state.lang == "日本語":
                explanation = (
                    f"{current_grade}-S{current_step} の給与は {format_money(current_salary)} です。"
                    f"AP は {format_money(ap_amount)}、PP は {format_money(pp_amount)} なので、"
                    f"昇格時の最低必要額は {format_money(current_salary)} + {format_money(ap_amount)} + {format_money(pp_amount)} = {format_money(minimum_required)} です。"
                    f"そのため、{target_grade} の中でこの金額を下回らず、最も近い金額となるのは {target_grade}-S{target_step}（{format_money(target_salary)}）です。"
                )
            else:
                explanation = (
                    f"The salary at {current_grade}-S{current_step} is {format_money(current_salary)}. "
                    f"AP is {format_money(ap_amount)} and PP is {format_money(pp_amount)}, so the minimum required amount is "
                    f"{format_money(current_salary)} + {format_money(ap_amount)} + {format_money(pp_amount)} = {format_money(minimum_required)}. "
                    f"Therefore, the closest step in {target_grade} that does not fall below this amount is {target_grade}-S{target_step} ({format_money(target_salary)})."
                )
            st.info(explanation)

            st.subheader(t("sim_detail_heading"))
            breakdown_df = pd.DataFrame([
                {t("sim_item"): t("sim_current_salary"), t("sim_amount"): current_salary},
                {t("sim_item"): "AP", t("sim_amount"): ap_amount},
                {t("sim_item"): "PP", t("sim_amount"): pp_amount},
                {t("sim_item"): t("min_required"), t("sim_amount"): minimum_required},
                {t("sim_item"): t("sim_target_salary"), t("sim_amount"): target_salary},
            ])
            breakdown_display = breakdown_df.copy()
            breakdown_display[t("sim_amount")] = breakdown_display[t("sim_amount")].apply(format_money)
            st.dataframe(breakdown_display, use_container_width=True, hide_index=True)

            search_df = current_df[["Step", target_grade]].copy()
            search_df["Eligible"] = search_df[target_grade] >= minimum_required
            st.subheader(t("step_search_result"))
            st.dataframe(search_df, use_container_width=True, hide_index=True)

# =========================================================
# Tab 5: Adjustment allowance calculation
# =========================================================
with tab5:
    st.subheader(t("adjustment_calc_heading"))
    st.markdown(f"<div class='info-card'>{t('adjustment_calc_text')}</div>", unsafe_allow_html=True)
    st.caption(t("adjustment_calc_result_text"))
    st.caption(lang_text("CSVは Taxable Allowance / Non-Taxable Allowance を分けて入力します。", "In the CSV, enter Taxable Allowance and Non-Taxable Allowance separately."))

    batch_template_csv = build_adjustment_batch_csv_template().to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        lang_text("一括計算CSVテンプレートをダウンロード", "Download batch calculation CSV template"),
        data=batch_template_csv,
        file_name="adjustment_batch_template.csv",
        mime="text/csv",
    )

    calc_university_allowance = st.number_input(
        t("univ_allowance"),
        min_value=0.0,
        value=0.0,
        step=100.0,
        key="adj_univ_allowance_batch",
    )
    uploaded_adj_csv = st.file_uploader(
        lang_text("調整手当計算CSVをアップロード", "Upload adjustment calculation CSV"),
        type=["csv"],
        key="adj_batch_csv_upload",
    )

    if uploaded_adj_csv is not None:
        try:
            uploaded_adj_csv.seek(0)
            preview_adj_df = pd.read_csv(uploaded_adj_csv)
            st.markdown(f"**{lang_text('CSVプレビュー', 'CSV Preview')}**")
            st.dataframe(preview_adj_df, use_container_width=True, hide_index=True)
        except Exception:
            st.error(lang_text("CSVの読み込みに失敗しました。", "Failed to read the CSV."))

    if st.button(t("adjustment_calc_run"), use_container_width=True, key="adjustment_calc_run_button"):
        if uploaded_adj_csv is None:
            st.warning(lang_text("CSVファイルを選択してください。", "Please choose a CSV file."))
        else:
            try:
                uploaded_adj_csv.seek(0)
                source_df = pd.read_csv(uploaded_adj_csv)
                validated_df = validate_adjustment_batch_csv(source_df)
                upload_df = build_adjustment_batch_upload_df(
                    validated_df,
                    area_wage_tables=all_area_wage_tables(),
                    university_allowance_amount=calc_university_allowance,
                )
                st.session_state.adjustment_upload_df = upload_df.copy()

                preview_df = upload_df.copy()
                for col in ["Adjustment Allowance", "Taxable Allowance", "Non-Taxable Allowance"]:
                    if col in preview_df.columns:
                        preview_df[col] = preview_df[col].apply(format_money)
                st.markdown(f"**{lang_text('出力プレビュー', 'Output Preview')}**")
                st.dataframe(preview_df, use_container_width=True, hide_index=True)

                upload_csv = upload_df.to_csv(index=False).encode("utf-8-sig")
                upload_excel = make_excel_file(upload_df)
                cd1, cd2 = st.columns(2)
                with cd1:
                    st.download_button(
                        t("adjustment_calc_download"),
                        data=upload_csv,
                        file_name="adjustment_batch_upload.csv",
                        mime="text/csv",
                        use_container_width=True,
                    )
                with cd2:
                    if upload_excel is not None:
                        st.download_button(
                            t("adjustment_calc_download_excel"),
                            data=upload_excel,
                            file_name="adjustment_batch_upload.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True,
                        )
                    else:
                        st.info(t("excel_unavailable"))
            except Exception as e:
                st.error(f"{lang_text('一括計算CSVの形式が正しくありません。', 'The batch calculation CSV format is invalid.')}\n\nDetail: {str(e)}")

# =========================================================
# Tab 6: Allowance export
# =========================================================
with tab6:
    st.subheader(t("allowance_export_heading"))
    st.write(f"{t('allowance_export_text')} ({area_label(st.session_state.selected_area)})")
    current_df = current_area_wage_df()
    ex1, ex2, ex3 = st.columns(3)
    with ex1:
        include_adjustment = st.checkbox(t("include_adjustment_allowance"), value=True)
        adjustment_amount = st.number_input(t("adjustment_allowance_export"), min_value=0.0, value=0.0, step=100.0)
    with ex2:
        include_university = st.checkbox(t("include_university_allowance"), value=False)
        university_amount = st.number_input(t("university_allowance_export"), min_value=0.0, value=0.0, step=100.0)
    with ex3:
        include_other = st.checkbox(t("include_other_allowance"), value=False)
        other_amount = st.number_input(t("other_allowance_export"), min_value=0.0, value=0.0, step=100.0)
    allowance_export_df = build_allowance_export_table(current_df, include_adjustment, adjustment_amount, include_university, university_amount, include_other, other_amount)
    st.dataframe(allowance_export_df, use_container_width=True, hide_index=True)
    allowance_csv = allowance_export_df.to_csv(index=False).encode("utf-8-sig")
    allowance_excel = make_excel_file(allowance_export_df)
    exd1, exd2 = st.columns(2)
    with exd1:
        st.download_button(t("export_with_allowances_csv"), data=allowance_csv, file_name=f"wage_table_with_allowances_{st.session_state.selected_area.lower().replace(' ', '_')}.csv", mime="text/csv", use_container_width=True)
    with exd2:
        if allowance_excel is not None:
            st.download_button(t("export_with_allowances_excel"), data=allowance_excel, file_name=f"wage_table_with_allowances_{st.session_state.selected_area.lower().replace(' ', '_')}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
        else:
            st.info(t("excel_unavailable"))

# =========================================================
# Tab 7: Employee roster
# =========================================================
with tab7:
    st.subheader(t("employee_heading"))
    st.markdown(f"<div class='info-card'>{t('employee_text')} {lang_text('エリア列を含めると、そのエリアの賃金テーブルが自動適用されます。', 'If the roster includes an Area column, the matching area wage table is applied automatically.')}</div>", unsafe_allow_html=True)
    st.caption(t("employee_net_note"))
    st.caption(lang_text("課税手当・非課税手当を分けて入力できます。旧CSVの Other Allowance は課税手当として読み込みます。", "You can separate taxable and non-taxable allowances. In legacy CSV files, Other Allowance is treated as Taxable Allowance."))
    template_emp_csv = build_employee_csv_template().to_csv(index=False).encode("utf-8-sig")
    st.download_button(t("employee_template_download"), data=template_emp_csv, file_name="employee_roster_template.csv", mime="text/csv")

    uploaded_emp_csv = None
    if not is_admin():
        st.markdown(f"<div class='warn-card'>{t('admin_only_upload_notice')}</div>", unsafe_allow_html=True)
        st.file_uploader(t("employee_upload"), type=["csv"], key="employee_csv_upload_disabled", disabled=True)
        st.button(t("employee_apply"), use_container_width=True, disabled=True, key="employee_apply_disabled")
    else:
        uploaded_emp_csv = st.file_uploader(t("employee_upload"), type=["csv"], key="employee_csv_upload")
        if uploaded_emp_csv is not None:
            try:
                uploaded_emp_csv.seek(0)
                preview_emp_df = pd.read_csv(uploaded_emp_csv)
                st.markdown(f"**{t('employee_preview')}**")
                st.dataframe(preview_emp_df, use_container_width=True, hide_index=True)
            except Exception:
                st.error(t("employee_import_error"))
        if st.button(t("employee_apply"), use_container_width=True):
            if uploaded_emp_csv is None:
                st.warning(t("employee_import_empty"))
            else:
                try:
                    uploaded_emp_csv.seek(0)
                    imported_emp_df = pd.read_csv(uploaded_emp_csv)
                    st.session_state.employee_roster_df = validate_employee_roster_csv(imported_emp_df)
                    st.success(t("employee_import_success"))
                except Exception as e:
                    st.error(f"{t('employee_import_error')}\n\nDetail: {str(e)}")

    if not st.session_state.employee_roster_df.empty and is_admin():
        active_only = st.checkbox(t("active_only"), value=True)
        roster_university_allowance = st.number_input(t("default_university_allowance"), min_value=0.0, value=0.0, step=100.0)
        payroll_df = build_employee_payroll(
            st.session_state.employee_roster_df,
            all_area_wage_tables(),
            university_allowance_amount=roster_university_allowance,
        )
        if active_only:
            active_mask = st.session_state.employee_roster_df["Active"].astype(int).tolist()
            payroll_df = payroll_df[[a == 1 for a in active_mask]].reset_index(drop=True)
        display_payroll_df = payroll_df.copy()
        money_cols = [
            t("employee_basic_pay"),
            t("employee_adjustment_allowance"),
            t("employee_taxable_allowance"),
            t("employee_non_taxable_allowance"),
            t("employee_university_allowance"),
            t("employee_total_allowance"),
            t("employee_total_pay"),
            t("employee_sss"),
            t("employee_philhealth"),
            t("employee_pagibig"),
            t("employee_taxable_income"),
            t("employee_withholding_tax"),
            t("employee_total_deductions"),
            t("employee_net_pay"),
        ]
        for col in money_cols:
            if col in display_payroll_df.columns:
                display_payroll_df[col] = display_payroll_df[col].apply(lambda x: format_money(x) if pd.notna(x) else "-")
        if "_active" in display_payroll_df.columns:
            display_payroll_df = display_payroll_df.drop(columns=["_active"])
        st.dataframe(display_payroll_df, use_container_width=True, hide_index=True)
        emp_csv = payroll_df.drop(columns=["_active"]).to_csv(index=False).encode("utf-8-sig")
        emp_excel = make_excel_file(payroll_df.drop(columns=["_active"]))
        e1, e2 = st.columns(2)
        with e1:
            st.download_button(t("employee_export_csv"), data=emp_csv, file_name="employee_payroll.csv", mime="text/csv", use_container_width=True)
        with e2:
            if emp_excel is not None:
                st.download_button(t("employee_export_excel"), data=emp_excel, file_name="employee_payroll.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
            else:
                st.info(t("excel_unavailable"))
    elif not is_admin():
        st.info("Employee CSV data is hidden for viewers. Only admins can upload, view, and export employee-level data.")

# =========================================================
# Tab 7: Admin
# =========================================================
with tab8:
    st.subheader(t("admin_heading"))
    st.markdown(f"<div class='info-card'>{t('admin_text')}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='warn-card'>{t('warning_rebuild')}</div>", unsafe_allow_html=True)

    if st.session_state.lang == "日本語":
        st.info("Base / AP / PP は全エリア共通です。G6-S1 は各エリアの最低日給から自動計算されます。")
        st.caption("他グレードの Step1 は、G6 との差額を維持したままエリアごとに自動でスライドします。")
        grade_col_label = "グレード"
        position_col_label = "役職"
        area_col_label = "エリア"
        min_wage_label = "最低日給"
        g6_monthly_label = "G6 Step1 月給"
    else:
        st.info("Base / AP / PP are shared across all areas. G6-S1 is calculated automatically from each area's daily minimum wage.")
        st.caption("Step1 for other grades shifts by area while keeping the same grade-to-grade gap from G6.")
        grade_col_label = "Grade"
        position_col_label = "Position"
        area_col_label = "Area"
        min_wage_label = "Daily Minimum Wage"
        g6_monthly_label = "G6 Step1 Monthly Base"

    settings_editor_df = pd.DataFrame([
        {
            grade_col_label: g,
            position_col_label: grade_label(g),
            t("base_salary"): float(st.session_state.params[g]["base"]),
            t("ap"): float(st.session_state.params[g]["ap"]),
            t("pp"): float(st.session_state.params[g]["pp"]),
        }
        for g in GRADES
    ])

    edited_settings_df = st.data_editor(
        settings_editor_df,
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        disabled=[grade_col_label, position_col_label] if is_admin() else True,
        column_config={
            grade_col_label: st.column_config.TextColumn(width="small"),
            position_col_label: st.column_config.TextColumn(width="medium"),
            t("base_salary"): st.column_config.NumberColumn(min_value=0.0, step=100.0, format="%.2f"),
            t("ap"): st.column_config.NumberColumn(min_value=0.0, step=50.0, format="%.2f"),
            t("pp"): st.column_config.NumberColumn(min_value=0.0, step=50.0, format="%.2f"),
        },
        key="admin_settings_grid",
    )

    area_wage_editor_df = pd.DataFrame([
        {
            area_col_label: area_label(area),
            "AreaKey": area,
            min_wage_label: float(st.session_state.area_min_wages[area]),
            g6_monthly_label: daily_to_monthly_base(st.session_state.area_min_wages[area]),
        }
        for area in AREAS
    ])

    st.markdown("---")
    st.subheader(lang_text("エリア別最低賃金設定", "Area Minimum Wage Settings"))
    edited_area_wage_df = st.data_editor(
        area_wage_editor_df,
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        disabled=["AreaKey", area_col_label, g6_monthly_label] if is_admin() else True,
        column_config={
            area_col_label: st.column_config.TextColumn(width="medium"),
            "AreaKey": st.column_config.TextColumn(width="small"),
            min_wage_label: st.column_config.NumberColumn(min_value=0.0, step=1.0, format="%.2f"),
            g6_monthly_label: st.column_config.NumberColumn(disabled=True, format="%.2f"),
        },
        key="admin_area_wages_grid",
    )

    if is_admin():
        tmp_params = {}
        for _, row in edited_settings_df.iterrows():
            g = str(row[grade_col_label]).strip()
            tmp_params[g] = {
                "base": float(row[t("base_salary")]),
                "ap": float(row[t("ap")]),
                "pp": float(row[t("pp")]),
            }

        tmp_area_wages = {}
        for _, row in edited_area_wage_df.iterrows():
            area = str(row["AreaKey"]).strip()
            tmp_area_wages[area] = float(row[min_wage_label])

        b1, b2, b3 = st.columns(3)
        with b1:
            if st.button(t("rebuild"), use_container_width=True):
                try:
                    save_and_rebuild(tmp_params, tmp_area_wages)
                    st.success(t("success_rebuild"))
                    st.rerun()
                except Exception as e:
                    st.error(f"{t('supabase_save_error')}\n\nDetail: {str(e)}")
        with b2:
            if st.button(t("reset"), use_container_width=True):
                try:
                    reset_params = {k: v.copy() for k, v in DEFAULT_PARAMS.items()}
                    reset_area_wages = DEFAULT_AREA_MIN_WAGES.copy()
                    save_and_rebuild(reset_params, reset_area_wages)
                    st.success(t("success_reset"))
                    st.rerun()
                except Exception as e:
                    st.error(f"{t('supabase_save_error')}\n\nDetail: {str(e)}")
        with b3:
            st.metric(lang_text("現在の選択エリア", "Current selected area"), area_label(st.session_state.selected_area))

        st.markdown("---")
        st.subheader(t("csv_import_heading"))
        st.markdown(f"<div class='info-card'>{t('csv_import_text')}</div>", unsafe_allow_html=True)
        template_csv = build_settings_csv_template().to_csv(index=False).encode("utf-8-sig")
        st.download_button(t("csv_template_download"), data=template_csv, file_name="wage_table_settings_template.csv", mime="text/csv")

        uploaded_csv = st.file_uploader(t("csv_upload"), type=["csv"], key="settings_csv_upload")
        if uploaded_csv is not None:
            try:
                uploaded_csv.seek(0)
                preview_df = pd.read_csv(uploaded_csv)
                st.markdown(f"**{t('csv_preview_heading')}**")
                st.dataframe(preview_df, use_container_width=True, hide_index=True)
            except Exception:
                st.error(t("csv_import_error"))
        if st.button(t("csv_apply"), use_container_width=True):
            if uploaded_csv is None:
                st.warning(t("csv_import_empty"))
            else:
                try:
                    uploaded_csv.seek(0)
                    imported_df = pd.read_csv(uploaded_csv)
                    new_params = validate_imported_settings_csv(imported_df)
                    save_and_rebuild(new_params, tmp_area_wages)
                    st.success(t("csv_import_success"))
                    st.rerun()
                except Exception as e:
                    st.error(f"{t('csv_import_error')}\n\nDetail: {str(e)}")
    else:
        st.info("Viewer mode: settings can be viewed here, but only admins can save changes.")

st.markdown("---")
st.caption("Created for bilingual wage table explanation, visual guidance, promotion simulation, area-based wage tables, employee roster import/export, CSV import, and Supabase persistence in Streamlit.")
