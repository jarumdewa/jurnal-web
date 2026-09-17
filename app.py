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
import hashlib


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




def _turso_exec(sql, params=()):
    """Execute INSERT/UPDATE/DELETE ke Turso. Return True kalau sukses."""
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
    return True


def q(sql, params=()):
    """Query Turso + konversi kolom angka ke integer."""
    df = _turso_http(sql, params)
    for col in df.columns:
        if col in NUMERIC_COLS:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    return df



# ---------- AUTH ----------
def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()


def get_users():
    try:
        users = st.secrets.get("users", {})
        return dict(users)
    except Exception:
        return {}


def check_login(username, password):
    users = get_users()
    if username not in users:
        return None
    stored = users[username].get("password", "")
    if hash_pw(password) == stored:
        return username
    return None


def login_screen():
    st.markdown("## 🔐 Login Jurnal Jarum Dewa")
    st.caption("Silakan login untuk mengakses dashboard")
    with st.form("login_form"):
        u = st.text_input("Username", placeholder="admin / viewer")
        p = st.text_input("Password", type="password")
        ok = st.form_submit_button("🔓 Login")
    if ok:
        user = check_login(u, p)
        if user:
            st.session_state.logged_in = True
            st.session_state.username = user
            st.success(f"Selamat datang, {user}!")
            import time
            time.sleep(0.5)
            st.rerun()
        else:
            st.error("❌ Username atau password salah")


def logout_button():
    if st.sidebar.button("🚪 Logout", use_container_width=True):
        for key in ["logged_in", "username", "role"]:
            st.session_state.pop(key, None)
        st.rerun()


def is_admin():
    return st.session_state.get("role") == "admin"


# ---------- CEK LOGIN ----------
if not st.session_state.get("logged_in"):
    login_screen()
    st.stop()

username = st.session_state.get("username", "")
st.session_state["role"] = "admin" if "admin" in username.lower() else "viewer"
ROLE = st.session_state["role"]


# ---------- SIDEBAR ----------
st.sidebar.title("💼 Jurnal Jarum Dewa")
st.sidebar.caption("Sistem Akuntansi UMKM")
st.sidebar.markdown("---")
st.sidebar.write(f"👤 **{username}**")
st.sidebar.caption(f"Role: {'🔑 Admin' if ROLE == 'admin' else '👁️ Viewer'}")
st.sidebar.markdown("---")

if ROLE == "admin":
    menu_list = ["🏠 Dashboard", "✏️ Input Transaksi", "🏦 Kelola Akun", "📝 Input Jurnal",
                 "📅 Transaksi", "💰 Akun Bank", "📒 COA",
                 "📗 Jurnal", "📊 Neraca Saldo"]
else:
    menu_list = ["🏠 Dashboard", "📅 Transaksi", "💰 Akun Bank", "📒 COA",
                 "📗 Jurnal", "📊 Neraca Saldo"]

menu = st.sidebar.radio("Menu", menu_list)
st.sidebar.markdown("---")
logout_button()

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



# ---------- INPUT TRANSAKSI ----------
elif menu == "✏️ Input Transaksi":
    st.title("✏️ Input Transaksi Baru")
    st.caption("Catat pemasukan / pengeluaran / piutang manual")

    try:
        df_ak = q("SELECT id, kode, nama FROM akun ORDER BY id")
        akun_list = [("", "-- Tanpa Akun --")] + [
            (str(r["id"]), f"@{r['kode']} — {r['nama']}")
            for _, r in df_ak.iterrows()
        ]
    except Exception:
        akun_list = [("", "-- Tanpa Akun --")]

    with st.form("form_transaksi", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            tgl = st.date_input("Tanggal", value=date.today())
            jenis = st.selectbox("Jenis", ["pengeluaran", "pemasukan", "piutang"])
        with col2:
            kategori = st.selectbox(
                "Kategori",
                ["makanan", "minuman", "transport", "belanja",
                 "kesehatan", "hiburan", "tagihan", "penjualan",
                 "operasional", "lainnya"],
            )
            akun_id = st.selectbox(
                "Akun Bank",
                options=[k for k, _ in akun_list],
                format_func=lambda x: dict(akun_list)[x],
            )

        deskripsi = st.text_input("Deskripsi", placeholder="cth: makan siang tim")
        jumlah_str = st.text_input("Jumlah (Rp)", placeholder="cth: 50000")

        submit = st.form_submit_button("Simpan")

    if submit:
        try:
            if not deskripsi or not jumlah_str:
                st.error("Deskripsi & jumlah wajib diisi")
            else:
                jumlah = int(jumlah_str.replace(".", "").replace(",", ""))
                akun_val = int(akun_id) if akun_id else None
                _turso_exec(
                    "INSERT INTO transaksi (user_id, tanggal, jenis, kategori, deskripsi, jumlah, akun_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (1, tgl.isoformat(), jenis, kategori, deskripsi, jumlah, akun_val),
                )
                st.success(f"Tersimpan: {jenis} {rp(jumlah)} - {deskripsi}")
                import time
                time.sleep(1)
                st.rerun()
        except Exception as e:
            st.error(f"Gagal simpan: {e}")

    st.markdown("---")
    st.caption("Untuk input massal atau via foto bon, tetap pakai bot Telegram")


# ---------- KELOLA AKUN ----------
elif menu == "🏦 Kelola Akun":
    st.title("🏦 Kelola Akun Bank / Rekening")
    st.caption("Tambah, edit, atau hapus akun")

    # Session state untuk edit mode
    if "edit_akun_id" not in st.session_state:
        st.session_state.edit_akun_id = None

    # ---------- FORM TAMBAH ----------
    with st.expander("➕ Tambah Akun Baru", expanded=st.session_state.edit_akun_id is None):
        with st.form("form_akun", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                kode = st.text_input("Kode", placeholder="cth: bca-762")
                nama = st.text_input("Nama", placeholder="cth: BCA David")
            with col2:
                jenis_ak = st.selectbox("Jenis", ["bank", "tabungan", "kartu_kredit", "cash"])
                saldo_awal_str = st.text_input("Saldo Awal", value="0")
            submit_ak = st.form_submit_button("💾 Tambah Akun")

        if submit_ak:
            try:
                if not kode or not nama:
                    st.error("Kode & nama wajib diisi")
                else:
                    saldo_awal = int(saldo_awal_str.replace(".", "").replace(",", "") or 0)
                    _turso_exec(
                        "INSERT INTO akun (user_id, kode, nama, jenis, saldo_awal) VALUES (?, ?, ?, ?, ?)",
                        (1, kode.lower(), nama, jenis_ak, saldo_awal),
                    )
                    st.success(f"✅ Akun @{kode} ditambahkan")
                    import time
                    time.sleep(1)
                    st.rerun()
            except Exception as e:
                st.error(f"Gagal: {e}")

    # ---------- FORM EDIT (muncul kalau ada yang diklik edit) ----------
    if st.session_state.edit_akun_id is not None:
        df_edit = q("SELECT id, kode, nama, jenis, saldo_awal FROM akun WHERE id=?",
                    (st.session_state.edit_akun_id,))
        if len(df_edit) > 0:
            r = df_edit.iloc[0]
            st.markdown("---")
            st.subheader(f"✏️ Edit Akun: @{r['kode']}")
            with st.form("form_edit_akun"):
                col1, col2 = st.columns(2)
                with col1:
                    kode_e = st.text_input("Kode", value=str(r["kode"]))
                    nama_e = st.text_input("Nama", value=str(r["nama"]))
                with col2:
                    jenis_opts = ["bank", "tabungan", "kartu_kredit", "cash"]
                    idx_j = jenis_opts.index(str(r["jenis"])) if str(r["jenis"]) in jenis_opts else 0
                    jenis_e = st.selectbox("Jenis", jenis_opts, index=idx_j)
                    saldo_awal_e = st.text_input("Saldo Awal", value=str(int(r["saldo_awal"])))

                cs1, cs2 = st.columns(2)
                with cs1:
                    submit_e = st.form_submit_button("💾 Simpan Perubahan")
                with cs2:
                    cancel_e = st.form_submit_button("❌ Batal")

            if submit_e:
                try:
                    saldo_awal_val = int(saldo_awal_e.replace(".", "").replace(",", "") or 0)
                    _turso_exec(
                        "UPDATE akun SET kode=?, nama=?, jenis=?, saldo_awal=? WHERE id=?",
                        (kode_e.lower(), nama_e, jenis_e, saldo_awal_val, int(r["id"])),
                    )
                    st.success(f"✅ Akun @{kode_e} diupdate")
                    st.session_state.edit_akun_id = None
                    import time
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Gagal: {e}")

            if cancel_e:
                st.session_state.edit_akun_id = None
                st.rerun()

    # ---------- DAFTAR AKUN ----------
    st.markdown("---")
    st.subheader("📋 Daftar Akun")
    df_ak = q("""
        SELECT a.id, a.kode, a.nama, a.jenis, a.saldo_awal,
            COALESCE(SUM(CASE WHEN t.jenis='pemasukan' AND t.akun_id=a.id THEN t.jumlah END),0) AS masuk,
            COALESCE(SUM(CASE WHEN t.jenis='pengeluaran' AND t.akun_id=a.id THEN t.jumlah END),0) AS keluar
        FROM akun a
        LEFT JOIN transaksi t ON t.akun_id = a.id
        GROUP BY a.id ORDER BY a.id
    """)

    if len(df_ak) > 0:
        df_ak["saldo"] = df_ak["saldo_awal"] + df_ak["masuk"] - df_ak["keluar"]

        for _, r in df_ak.iterrows():
            with st.container():
                c1, c2, c3, c4, c5 = st.columns([2, 3, 1.5, 2, 1.5])
                with c1:
                    st.write(f"**@{r['kode']}**")
                with c2:
                    st.write(f"{r['nama']}")
                with c3:
                    st.caption(f"{r['jenis']}")
                with c4:
                    st.write(f"**{rp(r['saldo'])}**")
                with c5:
                    c5a, c5b = st.columns(2)
                    with c5a:
                        if st.button("✏️", key=f"edit_{r['id']}", help="Edit"):
                            st.session_state.edit_akun_id = int(r["id"])
                            st.rerun()
                    with c5b:
                        if st.button("🗑️", key=f"del_{r['id']}", help="Hapus"):
                            try:
                                _turso_exec("DELETE FROM akun WHERE id=?", (int(r["id"]),))
                                st.success(f"Akun @{r['kode']} dihapus")
                                import time
                                time.sleep(1)
                                st.rerun()
                            except Exception as e:
                                st.error(f"Gagal: {e}")
    else:
        st.info("Belum ada akun.")



# ---------- INPUT JURNAL ----------
elif menu == "📝 Input Jurnal":
    st.title("📝 Input Jurnal Double-Entry")
    st.caption("Tiap baris = debit ATAU kredit (isi salah satu)")

    try:
        df_coa = q("SELECT kode, nama FROM coa ORDER BY kode")
        coa_list = [(str(r["kode"]), f"{r['kode']} - {r['nama']}") for _, r in df_coa.iterrows()]
    except Exception:
        coa_list = []

    with st.form("form_jurnal", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            tgl_j = st.date_input("Tanggal", value=date.today())
        with col2:
            desk_j = st.text_input("Deskripsi", placeholder="cth: jual exosome")

        st.markdown("**Baris Jurnal** (minimal 2 baris)")
        baris = []
        for i in range(4):
            c1, c2, c3 = st.columns([3, 2, 2])
            with c1:
                kode_j = st.selectbox(
                    f"Akun #{i+1}",
                    options=[""] + [k for k, _ in coa_list],
                    format_func=lambda x: dict(coa_list).get(x, "-- pilih --") if x else "-- pilih --",
                    key=f"j_coa_{i}",
                )
            with c2:
                debit_str = st.text_input(f"Debit #{i+1}", value="", key=f"j_d_{i}")
            with c3:
                kredit_str = st.text_input(f"Kredit #{i+1}", value="", key=f"j_k_{i}")
            baris.append((kode_j, debit_str, kredit_str))

        submit_j = st.form_submit_button("Posting Jurnal")

    if submit_j:
        try:
            lines = []
            for kode_j, d_str, k_str in baris:
                if not kode_j:
                    continue
                d = int(d_str.replace(".", "").replace(",", "") or 0)
                k = int(k_str.replace(".", "").replace(",", "") or 0)
                if d > 0 and k > 0:
                    st.error(f"Baris {kode_j}: isi debit ATAU kredit saja")
                    st.stop()
                if d == 0 and k == 0:
                    continue
                lines.append((kode_j, d, k))

            if len(lines) < 2:
                st.error("Minimal 2 baris")
                st.stop()

            total_d = sum(l[1] for l in lines)
            total_k = sum(l[2] for l in lines)
            if total_d != total_k:
                st.error(f"Tidak balance: Debit {rp(total_d)} != Kredit {rp(total_k)}")
                st.stop()

            _turso_exec(
                "INSERT INTO jurnal (user_id, tanggal, deskripsi) VALUES (?, ?, ?)",
                (1, tgl_j.isoformat(), desk_j),
            )
            df_last = q("SELECT id FROM jurnal ORDER BY id DESC LIMIT 1")
            jid = int(df_last["id"][0])
            for kode_j, d, k in lines:
                _turso_exec(
                    "INSERT INTO jurnal_detail (jurnal_id, coa_kode, debit, kredit) VALUES (?, ?, ?, ?)",
                    (jid, kode_j, d, k),
                )
            st.success(f"Jurnal #{jid} diposting (balance {rp(total_d)})")
            import time
            time.sleep(1)
            st.rerun()
        except Exception as e:
            st.error(f"Gagal: {e}")


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