import instaloader

# GANTI DENGAN AKUN TUMBAL/DUMMY ANDA
USER = "sheep.633618"
PASS = "Muh5y@!r"

L = instaloader.Instaloader()

try:
    print(f"🔄 Mencoba login sebagai {USER}...")
    L.login(USER, PASS)
    print("✅ Login Berhasil!")
    
    # Simpan session ke file
    L.save_session_to_file()
    print(f"📁 Session file disimpan di folder: {L.context.username}")
    print("Sekarang Anda bisa menjalankan app.py, session akan otomatis dipakai.")
    
except Exception as e:
    print(f"❌ Login Gagal: {e}")
    print("Saran: Coba login manual di HP dulu, atau gunakan akun lain.")