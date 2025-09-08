import tkinter as tk
from tkinter import filedialog, messagebox
from pydub import AudioSegment
import os
import time

def converter_mp3_para_wav():
    # Seleciona arquivo MP3
    caminho = filedialog.askopenfilename(filetypes=[("MP3 files", "*.mp3")])
    if caminho:
        try:
            # Mostra mensagem de "Iniciando conversão"
            status_label.config(text="🔄 Iniciando conversão...")
            janela.update()

            mp3 = AudioSegment.from_file(caminho, format="mp3")
            nome_base = os.path.splitext(os.path.basename(caminho))[0]
            pasta = os.path.dirname(caminho)

            # Pasta de saída "convertido_wav"
            output_folder = os.path.join(pasta, "convertido_wav")
            os.makedirs(output_folder, exist_ok=True)

            caminho_wav = os.path.join(output_folder, f"{nome_base}.wav")
            mp3.export(caminho_wav, format="wav")

            # Atualiza label para mostrar sucesso
            status_label.config(text=f"✅ Convertido: {nome_base}.mp3 → {caminho_wav}")
            messagebox.showinfo("Sucesso", f"Convertido com sucesso para:\n{caminho_wav}")

        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao converter: {e}")
            status_label.config(text="❌ Erro na conversão")
    else:
        status_label.config(text="Nenhum arquivo selecionado")

# Configuração da janela
janela = tk.Tk()
janela.title("🎧 MOCADO - CONVERSOR DE ÁUDIO 🎧")
janela.geometry("600x250")
janela.resizable(False, False)

# Frame para layout
frame = tk.Frame(janela, padx=20, pady=20)
frame.pack(expand=True, fill="both")

# Título estilo ASCII box como label (sem borda real, só visual)
titulo = """
╔════════════════════════════════════════════╗
║     🎧  MOCADO - CONVERSOR DE ÁUDIO 🎧    ║
╠════════════════════════════════════════════╣
║   APP MOCADO RECORDS - DIREITOS RESERVADOS  ║
╚════════════════════════════════════════════╝
"""
label_titulo = tk.Label(frame, text=titulo, font=("Courier New", 12), justify="center")
label_titulo.pack()

# Espaço
tk.Label(frame, text="").pack()

# Botão para converter
botao_converter = tk.Button(frame, text="Selecionar MP3 e Converter", font=("Arial", 14), command=converter_mp3_para_wav)
botao_converter.pack(pady=10)

# Label para mostrar status de operação
status_label = tk.Label(frame, text="", font=("Arial", 12), fg="green")
status_label.pack(pady=10)

# Rodar a janela
janela.mainloop()
