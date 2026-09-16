import os
import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import date, datetime, timedelta
from dotenv import load_dotenv

# ---------- TURSO ----------
try:
    TURSO_URL = st.secrets["TURSO_URL"]
    TURSO_TOKEN = st.secrets["TURSO_TOKEN"]
except Exception:
    load_dotenv(Path(__file__).parent / ".env.turso")
    TURSO_URL = os.getenv("TURSO_URL", "")
    TURSO_TOKEN = os.getenv("TURSO_TOKEN", "")

if not TURSO_URL or not TURSO_TOKEN:
    st.error("TURSO_URL / TURSO_TOKEN belum di-set. Cek secrets / .env.turso")
    st.stop()

import requests


# ---------- KONFIG ----------
st.set_page_config(
    page_title="Jurnal Jarum Dewa",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded",
)


def rp(n):
    try:
        return "Rp" + f"{int(n):,}".replace(",", ".")
    except Exception:
        return "Rp0"


def _turso_http(sql, params=()):
    """Query Turso via HTTP API."""
    url = TURSO_URL.replace("libsql://", "https://") + "/v2/pipeline"
    headers = {
        "Authorization": f"Bearer {TURSO_TOKEN}",
        "Content-Type": "application/json",
    }
    args = []
    for p in params:
        if p is None:
            args.append({"type": "null"})
        elif isinstance(p, int):
            args.append({"type": "integer", "value": str(p)})
        elif isinstance(p, float):
            args.append({"type": "float", "value": p})
        else:
            args.append({"type": "text", "value": str(p)})

    payload = {
        "requests": [
            {"type": "execute", "stmt": {"sql": sql, "args": args}},
            {"type": "close"},
        ]
    }
    r = requests.post(url, headers=headers, json=payload, timeout=30)
    r.raise_for_status()
    data = r.json()

    result = data["results"][0]
    if result.get("type") == "error":
        raise Exception(result.get("error", {}).get("message", "Turso error"))

    resp = result["response"]["result"]
    cols = [c["name"] for c in resp["cols"]]
    rows = []
    for row in resp["rows"]:
        rows.append(tuple(cell.get("value") for cell in row))
    return pd.DataFrame(rows, columns=cols)


NUMERIC_COLS = {
    "id", "user_id", "akun_id", "akun_lawan_id", "jurnal_id",
    "jumlah", "saldo_awal", "masuk", "keluar", "debit", "kredit",
    "total", "tdebit", "tkredit",
}


def q(sql, params=()):
    """Query Turso + konversi kolom angka ke integer."""
    df = _turso_http(sql, params)
    for col in df.columns:
        if col in NUMERIC_COLS:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    return df


# ---------- SIDEBAR ----------
st.sidebar.title("💼 Jurnal Jarum Dewa")
st.sidebar.caption("Sistem Akuntansi UMKM")
st.sidebar.markdown("---")

menu = st.sidebar.radio(
    "Menu",
    ["🏠 Dashboard", "📅 Transaksi", "💰 Akun Bank", "📒 COA",
     "📗 Jurnal", "📊 Neraca Saldo"],
)

st.sidebar.markdown("---")
st.sidebar.caption(f"📅 {date.today().isoformat()}")
st.sidebar.caption("☁️ Turso Cloud")


# ---------- DASHBOARD ----------
if menu == "🏠 Dashboard":
    st.title("🏠 Dashboard")
    st.caption(f"Hari ini: {datetime.now().strftime('%A, %d %B %Y')}")

    try:
        df_saldo = q("""
            SELECT
                COALESCE(SUM(CASE WHEN jenis='pemasukan' THEN jumlah END),0) AS masuk,
                COALESCE(SUM(CASE WHEN jenis='pengeluaran' THEN jumlah END),0) AS keluar,
                COALESCE(SUM(CASE WHEN jenis='piutang' THEN jumlah END),0) AS piutang
            FROM transaksi
        """)
        masuk = int(df_saldo["masuk"][0] or 0)
        keluar = int(df_saldo["keluar"][0] or 0)
        piutang = int(df_saldo["piutang"][0] or 0)
        saldo = masuk - keluar

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("💰 Saldo", rp(saldo))
        c2.metric("⬆️ Masuk", rp(masuk))
        c3.metric("⬇️ Keluar", rp(keluar))
        c4.metric("📋 Piutang", rp(piutang))

        st.markdown("---")
        st.subheader("🏦 Saldo Per Akun")

        df_akun = q("""
            SELECT
                a.kode, a.nama, a.jenis, a.saldo_awal,
                COALESCE(SUM(CASE WHEN t.jenis='pemasukan' AND t.akun_id=a.id THEN t.jumlah END),0) AS masuk,
                COALESCE(SUM(CASE WHEN t.jenis='pengeluaran' AND t.akun_id=a.id THEN t.jumlah END),0) AS keluar
            FROM akun a
            LEFT JOIN transaksi t ON t.akun_id = a.id
            GROUP BY a.id
            ORDER BY a.id
        """)
        if len(df_akun) > 0:
            df_akun["saldo"] = df_akun["saldo_awal"] + df_akun["masuk"] - df_akun["keluar"]
            df_show = df_akun.copy()
            df_show["Saldo Awal"] = df_show["saldo_awal"].apply(rp)
            df_show["Masuk"] = df_show["masuk"].apply(rp)
            df_show["Keluar"] = df_show["keluar"].apply(rp)
            df_show["Saldo"] = df_show["saldo"].apply(rp)
            st.dataframe(
                df_show[["kode", "nama", "jenis", "Saldo Awal", "Masuk", "Keluar", "Saldo"]].rename(
                    columns={"kode": "Kode", "nama": "Nama", "jenis": "Jenis"}
                ),
                use_container_width=True, hide_index=True,
            )
            st.metric("Total Semua Akun", rp(int(df_akun["saldo"].sum())))

        st.markdown("---")
        col1, col2 = st.columns([2, 1])

        with col1:
            st.subheader("📅 Transaksi 30 Hari Terakhir")
            df_trx = q("""
                SELECT id, tanggal, jenis, kategori, deskripsi, toko, jumlah
                FROM transaksi
                WHERE tanggal >= date('now', '-30 days')
                ORDER BY tanggal DESC, id DESC
                LIMIT 50
            """)
            if len(df_trx) > 0:
                df_trx["J"] = df_trx["jenis"].map({
                    "pemasukan": "⬆️", "pengeluaran": "⬇️",
                    "piutang": "📋", "pindah": "🔄"
                }).fillna("•")
                df_trx["Jumlah"] = df_trx["jumlah"].apply(rp)
                st.dataframe(
                    df_trx[["id", "tanggal", "J", "deskripsi", "toko", "Jumlah"]].rename(
                        columns={"id": "ID", "tanggal": "Tgl", "J": "J",
                                 "deskripsi": "Deskripsi", "toko": "Toko"}
                    ),
                    use_container_width=True, hide_index=True,
                )

        with col2:
            st.subheader("📊 Kategori (30 hari)")
            df_kat = q("""
                SELECT kategori, SUM(jumlah) AS total
                FROM transaksi
                WHERE jenis='pengeluaran' AND tanggal >= date('now', '-30 days')
                GROUP BY kategori ORDER BY total DESC
            """)
            if len(df_kat) > 0:
                df_kat["Total"] = df_kat["total"].apply(rp)
                st.dataframe(
                    df_kat[["kategori", "Total"]].rename(columns={"kategori": "Kategori"}),
                    use_container_width=True, hide_index=True,
                )
                try:
                    import plotly.express as px
                    fig = px.pie(df_kat, values="total", names="kategori", hole=0.4)
                    fig.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=0))
                    st.plotly_chart(fig, use_container_width=True)
                except Exception:
                    pass

    except Exception as e:
        st.error(f"Error: {e}")
        st.exception(e)


# ---------- TRANSAKSI ----------
elif menu == "📅 Transaksi":
    st.title("📅 Semua Transaksi")
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        dari = st.date_input("Dari", value=date.today() - timedelta(days=90))
    with col2:
        sampai = st.date_input("Sampai", value=date.today())
    with col3:
        jenis = st.selectbox("Jenis", ["Semua", "pemasukan", "pengeluaran", "piutang", "pindah"])

    sql = "SELECT id, tanggal, jenis, kategori, deskripsi, toko, jumlah FROM transaksi WHERE tanggal BETWEEN ? AND ?"
    params = [dari.isoformat(), sampai.isoformat()]
    if jenis != "Semua":
        sql += " AND jenis=?"
        params.append(jenis)
    sql += " ORDER BY tanggal DESC, id DESC LIMIT 500"

    df = q(sql, params)
    if len(df) > 0:
        df["Jumlah"] = df["jumlah"].apply(rp)
        st.dataframe(
            df[["id", "tanggal", "jenis", "kategori", "deskripsi", "toko", "Jumlah"]].rename(
                columns={"id": "ID", "tanggal": "Tgl"}
            ),
            use_container_width=True, hide_index=True,
        )
        c1, c2 = st.columns(2)
        total_masuk = df[df["jenis"] == "pemasukan"]["jumlah"].sum() if "jumlah" in df.columns else 0
        total_keluar = df[df["jenis"] == "pengeluaran"]["jumlah"].sum() if "jumlah" in df.columns else 0
        c1.metric("Total Masuk", rp(total_masuk))
        c2.metric("Total Keluar", rp(total_keluar))
        st.caption(f"{len(df)} transaksi")
    else:
        st.info("Tidak ada transaksi.")


# ---------- AKUN BANK ----------
elif menu == "💰 Akun Bank":
    st.title("💰 Akun Bank / Rekening")
    df = q("""
        SELECT a.id, a.kode, a.nama, a.jenis, a.saldo_awal,
            COALESCE(SUM(CASE WHEN t.jenis='pemasukan' AND t.akun_id=a.id THEN t.jumlah END),0) AS masuk,
            COALESCE(SUM(CASE WHEN t.jenis='pengeluaran' AND t.akun_id=a.id THEN t.jumlah END),0) AS keluar
        FROM akun a
        LEFT JOIN transaksi t ON t.akun_id = a.id
        GROUP BY a.id ORDER BY a.id
    """)
    if len(df) > 0:
        df["saldo"] = df["saldo_awal"] + df["masuk"] - df["keluar"]
        st.metric("Total Semua Akun", rp(int(df["saldo"].sum())))
        df_show = df.copy()
        df_show["Saldo Awal"] = df_show["saldo_awal"].apply(rp)
        df_show["Masuk"] = df_show["masuk"].apply(rp)
        df_show["Keluar"] = df_show["keluar"].apply(rp)
        df_show["Saldo"] = df_show["saldo"].apply(rp)
        st.dataframe(
            df_show[["kode", "nama", "jenis", "Saldo Awal", "Masuk", "Keluar", "Saldo"]].rename(
                columns={"kode": "Kode", "nama": "Nama", "jenis": "Jenis"}
            ),
            use_container_width=True, hide_index=True,
        )
    else:
        st.info("Belum ada akun.")


# ---------- COA ----------
elif menu == "📒 COA":
    st.title("📒 Chart of Accounts")
    df = q("SELECT kode, nama, jenis, saldo_normal FROM coa ORDER BY kode")
    if len(df) > 0:
        for jenis in ["aset", "kewajiban", "ekuitas", "pendapatan", "hpp", "beban"]:
            sub = df[df["jenis"] == jenis]
            if len(sub) > 0:
                st.subheader(jenis.upper())
                st.dataframe(
                    sub[["kode", "nama", "saldo_normal"]].rename(
                        columns={"kode": "Kode", "nama": "Nama", "saldo_normal": "Saldo Normal"}
                    ),
                    use_container_width=True, hide_index=True,
                )
    else:
        st.info("COA kosong.")


# ---------- JURNAL ----------
elif menu == "📗 Jurnal":
    st.title("📗 Jurnal Umum")
    df = q("""
        SELECT j.id, j.tanggal, j.deskripsi, c.nama AS akun, jd.debit, jd.kredit
        FROM jurnal j
        JOIN jurnal_detail jd ON jd.jurnal_id = j.id
        LEFT JOIN coa c ON c.kode = jd.coa_kode
        ORDER BY j.tanggal DESC, j.id DESC, jd.id
        LIMIT 200
    """)
    if len(df) > 0:
        df["Debit"] = df["debit"].apply(lambda x: rp(x) if x and x != 0 else "-")
        df["Kredit"] = df["kredit"].apply(lambda x: rp(x) if x and x != 0 else "-")
        st.dataframe(
            df[["id", "tanggal", "deskripsi", "akun", "Debit", "Kredit"]].rename(
                columns={"id": "JID", "tanggal": "Tgl", "deskripsi": "Keterangan", "akun": "Akun"}
            ),
            use_container_width=True, hide_index=True,
        )
    else:
        st.info("Belum ada jurnal.")


# ---------- NERACA SALDO ----------
elif menu == "📊 Neraca Saldo":
    st.title("📊 Neraca Saldo")
    df = q("""
        SELECT c.kode, c.nama, c.saldo_normal,
            COALESCE(SUM(jd.debit),0) AS tdebit,
            COALESCE(SUM(jd.kredit),0) AS tkredit
        FROM coa c
        LEFT JOIN jurnal_detail jd ON jd.coa_kode = c.kode
        GROUP BY c.kode ORDER BY c.kode
    """)
    rows = []
    td = tk = 0
    for _, r in df.iterrows():
        tdebit = float(r["tdebit"]) if r["tdebit"] is not None else 0
        tkredit = float(r["tkredit"]) if r["tkredit"] is not None else 0
        if r["saldo_normal"] == "debit":
            d, k = tdebit - tkredit, 0
        else:
            d, k = 0, tkredit - tdebit
        if d == 0 and k == 0:
            continue
        rows.append({"Kode": r["kode"], "Nama": r["nama"], "Debit": rp(d), "Kredit": rp(k)})
        td += d
        tk += k
    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Debit", rp(td))
        c2.metric("Total Kredit", rp(tk))
        if int(td) == int(tk):
            c3.success("✅ Balance")
        else:
            c3.error(f"⚠️ Selisih {rp(abs(td - tk))}")
    else:
        st.info("Belum ada jurnal.")