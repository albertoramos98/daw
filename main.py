import customtkinter as ctk
from app import App # Importa nossa classe principal do arquivo app.py

# --- PONTO DE ENTRADA DO PROGRAMA ---
if __name__ == "__main__":
    # Define o tema antes de criar a janela principal
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    
    app = App()
    app.mainloop()