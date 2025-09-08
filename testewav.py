import os
import time
from pydub import AudioSegment

# Tela de abertura
os.system('cls' if os.name == 'nt' else 'clear')
print("""
╔════════════════════════════════════════════╗
║     🎧  MOCADO - CONVERSOR DE ÁUDIO 🎧    ║
╠════════════════════════════════════════════╣
║   APP MOCADO RECORDS - DIREITOS RESERVADOS  ║
╚════════════════════════════════════════════╝
""")
print("🔄 Iniciando conversão...\n")
time.sleep(1.5)

# Conversão
output_folder = "convertido_wav"
os.makedirs(output_folder, exist_ok=True)

for filename in os.listdir():
    if filename.endswith(".mp3"):
        mp3_path = os.path.join(os.getcwd(), filename)
        wav_path = os.path.join(output_folder, filename.replace(".mp3", ".wav"))
        sound = AudioSegment.from_mp3(mp3_path)
        sound.export(wav_path, format="wav")
        print(f"✅ Convertido: {filename} ➜ {wav_path}")

print("\n🚀 Finalizado! Seus arquivos estão em:", output_folder)
input("\nPressione ENTER para sair...")
