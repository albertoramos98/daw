import customtkinter as ctk
import random
import sounddevice as sd
import numpy as np
from scipy.io.wavfile import write, read
import threading
import time
import matplotlib.pyplot as plt
from PIL import Image
import os

# --- CONFIGURAÇÃO INICIAL ---
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")
SAMPLE_RATE = 44100
CHANNELS = 1

# --- CLASSES DOS COMPONENTES DA UI ---

class TrackFrame(ctk.CTkFrame):
    """Uma classe para representar uma única trilha de áudio na UI."""
    def __init__(self, master, track_name):
        # Correção 1 (SyntaxError): Aspa adicionada na cor
        super().__init__(master, height=100, fg_color=random.choice(["#2E4053", "#512E53", "#2E5345", "#532E2E"]))
        
        self.track_name = track_name
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=5)
        self.name_label = ctk.CTkLabel(self, text=self.track_name, font=("Arial", 12))
        self.name_label.grid(row=0, column=0, padx=10, pady=10, sticky="nw")
        self.mute_button = ctk.CTkButton(self, text="M", width=30)
        self.mute_button.grid(row=1, column=0, padx=10, pady=5, sticky="nw")
        self.clips_area = ctk.CTkFrame(self, fg_color="#343638")
        self.clips_area.grid(row=0, column=1, rowspan=2, padx=10, pady=10, sticky="nsew")
        self.waveform_label = ctk.CTkLabel(self.clips_area, text="")
        self.waveform_label.pack(fill="both", expand=True)

        self.audio_file_path = None

    def display_waveform(self, image_path):
        """Carrega uma imagem e a exibe na área de clips, redimensionando."""
        try:
            width = self.clips_area.winfo_width()
            height = self.clips_area.winfo_height()
            
            if width <= 1 or height <= 1:
                self.after(50, lambda: self.display_waveform(image_path))
                return

            img_data = Image.open(image_path).resize((width, height), Image.Resampling.LANCZOS)
            ctk_img = ctk.CTkImage(light_image=img_data, dark_image=img_data, size=(width, height))
            
            self.waveform_label.configure(image=ctk_img, text="")
            self.waveform_label.image = ctk_img
        except Exception as e:
            print(f"Erro ao exibir a imagem: {e}")

class ContentFrame(ctk.CTkFrame):
    """O painel principal que vai conter as trilhas."""
    def __init__(self, master):
        super().__init__(master, corner_radius=0)
        self.scrollable_frame = ctk.CTkScrollableFrame(self, label_text="Trilhas")
        self.scrollable_frame.pack(fill="both", expand=True, padx=10, pady=10)
    def add_new_track(self, track_name):
        track = TrackFrame(self.scrollable_frame, track_name)
        track.pack(fill="x", expand=True, padx=5, pady=5)
        return track

class TransportFrame(ctk.CTkFrame):
    """O painel com os botões de Play, Stop, Record."""
    def __init__(self, master, play_command, stop_command, record_command):
        super().__init__(master, height=50, corner_radius=0)
        self.play_button = ctk.CTkButton(self, text="▶ Play", command=play_command)
        self.play_button.pack(side="left", padx=10, pady=10)
        self.stop_button = ctk.CTkButton(self, text="■ Stop", command=stop_command)
        self.stop_button.pack(side="left", padx=10, pady=10)
        self.record_button = ctk.CTkButton(self, text="● Rec", command=record_command, fg_color="#C0392B", hover_color="#E74C3C")
        self.record_button.pack(side="left", padx=10, pady=10)

# --- CLASSE PRINCIPAL DA APLICAÇÃO ---
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("DAW Pernambucana")
        self.geometry("1200x800")
        
        # Correção 2 (AttributeError): Removido o '_' das funções de grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=3)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)
        
        # --- DADOS E ESTADO DA APLICAÇÃO ---
        self.tracks = []
        self.track_count = 0
        self.output_filename_count = 1
        self.active_recording_track = None
        self.is_recording = False
        self.recording_frames = []
        self.recording_thread = None
        self.is_playing = False
        self.playback_thread = None

        # --- CRIAÇÃO DOS COMPONENTES DA UI ---
        self.browser_frame = ctk.CTkFrame(self, corner_radius=0)
        self.browser_frame.grid(row=0, column=0, rowspan=2, sticky="nsew")
        self.browser_label = ctk.CTkLabel(self.browser_frame, text="Browser")
        self.browser_label.pack(padx=20, pady=20)
        self.add_track_button = ctk.CTkButton(self.browser_frame, text="Adicionar Trilha", command=self.add_track)
        self.add_track_button.pack(padx=20, pady=10, side="bottom")

        self.transport_frame = TransportFrame(self, self.play_music, self.stop_music, self.record_audio)
        self.transport_frame.grid(row=1, column=1, sticky="nsew", padx=10, pady=10)
        
        self.content_frame = ContentFrame(self)
        self.content_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=(10,0))
    
    # --- THREAD WORKERS (Os "Assistentes") ---
    def _record_worker(self):
        """Função que será executada na thread de gravação."""
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS) as stream:
            print("Thread de gravação iniciada.")
            while self.is_recording:
                frames, overflowed = stream.read(SAMPLE_RATE // 10)
                if overflowed: print("Atenção! Overflow na captura de áudio.")
                self.recording_frames.append(frames)
        print("Thread de gravação finalizada.")

    def _play_worker(self, audio_data):
        """Função que será executada na thread de playback."""
        print("Thread de playback iniciada.")
        try:
            sd.play(audio_data, SAMPLE_RATE)
            sd.wait()
        except Exception as e:
            print(f"Erro durante o playback: {e}")
        finally:
            self.is_playing = False
            print("Thread de playback finalizada.")

    # --- FUNÇÕES AUXILIARES ---
    def _generate_waveform_image(self, wav_path, image_path):
        """Lê um arquivo .wav e salva um gráfico da sua onda como .png."""
        try:
            samplerate, data = read(wav_path)
            fig, ax = plt.subplots(figsize=(8, 1.5))
            ax.plot(data, color='cyan')
            ax.axis('off')
            fig.patch.set_facecolor('#343638')
            plt.savefig(image_path, bbox_inches='tight', pad_inches=0, dpi=100)
            plt.close(fig)
            return True
        except Exception as e:
            print(f"Erro ao gerar a imagem da onda: {e}")
            return False
            
    def add_track(self):
        """Adiciona uma nova trilha ao projeto."""
        self.track_count += 1
        track_name = f"Trilha {self.track_count}"
        new_track = self.content_frame.add_new_track(track_name)
        self.tracks.append(new_track)

    # --- MÉTODOS DE LÓGICA DO TRANSPORTE ---
    def play_music(self):
        """Toca o áudio da última trilha gravada."""
        if self.is_playing or self.is_recording:
            print("Aguarde a operação atual terminar.")
            return
        
        if not self.tracks:
            print("Nenhuma trilha para tocar.")
            return
        
        target_track = self.tracks[-1]

        if target_track.audio_file_path and os.path.exists(target_track.audio_file_path):
            print(f"▶ Tocando áudio de '{target_track.audio_file_path}'...")
            samplerate, audio_data = read(target_track.audio_file_path)
            self.is_playing = True
            self.playback_thread = threading.Thread(target=self._play_worker, args=(audio_data,))
            self.playback_thread.start()
        else:
            print("A trilha selecionada não tem áudio gravado.")

    def stop_music(self):
        """Para a gravação ou o playback em andamento."""
        if self.is_recording:
            print("■ Parando a gravação...")
            self.is_recording = False
            self.recording_thread.join()
            audio_data = np.concatenate(self.recording_frames, axis=0)

            wav_filename = f"gravacao_{self.output_filename_count}.wav"
            png_filename = f"gravacao_{self.output_filename_count}.png"
            self.output_filename_count += 1
            
            write(wav_filename, SAMPLE_RATE, audio_data)
            print(f"Áudio salvo em '{wav_filename}'")

            if self.active_recording_track:
                self.active_recording_track.audio_file_path = wav_filename
                if self._generate_waveform_image(wav_filename, png_filename):
                    self.active_recording_track.display_waveform(png_filename)
                self.active_recording_track = None

        elif self.is_playing:
            print("■ Parando o playback...")
            sd.stop()
            self.is_playing = False
        else:
            print("Nada para parar.")

    def record_audio(self):
        """Inicia a gravação na última trilha criada."""
        if self.is_recording or self.is_playing:
            print("Aguarde a operação atual terminar.")
            return
        
        if not self.tracks:
            print("Crie uma trilha antes de gravar!")
            return

        print("● Iniciando gravação...")
        self.is_recording = True
        self.recording_frames = []
        self.active_recording_track = self.tracks[-1]
        self.recording_thread = threading.Thread(target=self._record_worker)
        self.recording_thread.start()

if __name__ == "__main__":
    app = App()
    app.mainloop()