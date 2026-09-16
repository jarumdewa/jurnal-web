# Jurnal Jarum Dewa

Sistem akuntansi UMKM berbasis Streamlit + Turso Cloud.

## Fitur
- Dashboard saldo & transaksi
- Akun bank multi-rekening
- Chart of Accounts (COA)
- Jurnal Umum (double-entry)
- Neraca Saldo

## Setup Lokal

1. pip install -r requirements.txt
2. Buat file .env.turso dengan TURSO_URL dan TURSO_TOKEN
3. streamlit run app.py

## Deploy Streamlit Cloud

Set secrets di Streamlit Cloud:
- TURSO_URL
- TURSO_TOKEN
