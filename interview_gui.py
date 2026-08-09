"""
AI Interview Agent — ChatGPT-style Chat Interface
With proper conversation flow like DeepSeek/ChatGPT
"""

import asyncio
import inspect
import json
import os
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import uuid
from datetime import datetime
import webbrowser

# Try to import matplotlib
try:
    import matplotlib
    matplotlib.use("TkAgg")
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("Warning: matplotlib not installed. Charts will be disabled.")

# Try to import the interview agent
try:
    import main as agent
    AGENT_AVAILABLE = True
except ImportError:
    AGENT_AVAILABLE = False
    print("Error: main.py not found. Make sure it's in the same folder.")

# Constants
CANDIDATES_FILE = "candidates.json"
APP_NAME = "AI Interview Agent"
VERSION = "2.0.0"

# Color schemes
LIGHT_THEME = {
    'primary': '#2C3E50',
    'secondary': '#3498DB',
    'accent': '#E74C3C',
    'success': '#27AE60',
    'warning': '#F39C12',
    'background': '#F0F2F5',
    'surface': '#FFFFFF',
    'text': '#1A1A2E',
    'text_secondary': '#7F8C8D',
    'border': '#E4E6EB',
    'hover': '#2980B9',
    'chat_bg': '#F0F2F5',
    'user_bubble': '#0084FF',
    'user_text': '#FFFFFF',
    'ai_bubble': '#FFFFFF',
    'ai_text': '#1A1A2E',
    'header_text': 'white',
    'input_bg': '#FFFFFF',
    'input_border': '#E4E6EB',
}

DARK_THEME = {
    'primary': '#1A1A2E',
    'secondary': '#0F3460',
    'accent': '#E94560',
    'success': '#2ECC71',
    'warning': '#F39C12',
    'background': '#1A1A2E',
    'surface': '#16213E',
    'text': '#FFFFFF',
    'text_secondary': '#A0AEC0',
    'border': '#2D3748',
    'hover': '#1A365D',
    'chat_bg': '#1A1A2E',
    'user_bubble': '#0084FF',
    'user_text': '#FFFFFF',
    'ai_bubble': '#2D3748',
    'ai_text': '#FFFFFF',
    'header_text': '#FFFFFF',
    'input_bg': '#2D3748',
    'input_border': '#4A5568',
}

class ThemeManager:
    def __init__(self):
        self.current_theme = 'light'
        self.themes = {
            'light': LIGHT_THEME,
            'dark': DARK_THEME
        }
    
    def get_colors(self):
        return self.themes[self.current_theme]
    
    def toggle(self):
        self.current_theme = 'dark' if self.current_theme == 'light' else 'light'
        return self.get_colors()

def call_agent(func, *args, **kwargs):
    result = func(*args, **kwargs)
    if inspect.iscoroutine(result):
        result = asyncio.run(result)
    return result

class ChatMessage:
    """Chat message bubble with proper styling"""
    def __init__(self, parent, sender, text, time, colors):
        self.frame = tk.Frame(parent, bg=colors['chat_bg'])
        self.frame.pack(fill='x', pady=5, padx=10)
        
        # Create bubble
        bubble = tk.Frame(
            self.frame,
            bg=colors['user_bubble'] if sender == 'user' else colors['ai_bubble'],
            relief='flat',
            bd=0
        )
        
        # Align bubbles
        if sender == 'user':
            bubble.pack(side='right', anchor='e', padx=(50, 0))
            bubble_frame = tk.Frame(bubble, bg=colors['user_bubble'])
            text_color = colors['user_text']
        else:
            bubble.pack(side='left', anchor='w', padx=(0, 50))
            bubble_frame = tk.Frame(bubble, bg=colors['ai_bubble'])
            text_color = colors['ai_text']
        
        # Sender label
        sender_label = tk.Label(
            bubble_frame,
            text="You" if sender == 'user' else "Interviewer",
            font=('Segoe UI', 8, 'bold'),
            fg=colors['text_secondary'],
            bg=bubble['bg'],
            anchor='w'
        )
        sender_label.pack(anchor='w', padx=12, pady=(8, 0))
        
        # Message text
        msg_label = tk.Label(
            bubble_frame,
            text=text,
            font=('Segoe UI', 10),
            fg=text_color,
            bg=bubble['bg'],
            wraplength=500,
            justify='left'
        )
        msg_label.pack(anchor='w', padx=12, pady=(2, 8))
        
        # Time
        time_label = tk.Label(
            bubble_frame,
            text=time,
            font=('Segoe UI', 7),
            fg=colors['text_secondary'],
            bg=bubble['bg']
        )
        time_label.pack(anchor='e', padx=12, pady=(0, 6))
        
        # Pack bubble
        bubble_frame.pack(padx=4, pady=4)
        
        # Store reference
        self.bubble = bubble
        self.frame_ref = self.frame

class ModernButton(tk.Button):
    def __init__(self, master, **kwargs):
        self.theme_manager = kwargs.pop('theme_manager', None)
        self.default_bg = kwargs.pop('bg', None)
        self.hover_bg = kwargs.pop('hover_bg', None)
        
        super().__init__(master, **kwargs)
        
        if not self.default_bg:
            colors = self.theme_manager.get_colors() if self.theme_manager else LIGHT_THEME
            self.default_bg = colors['secondary']
            self.hover_bg = colors['hover']
        
        self.default_fg = kwargs.pop('fg', 'white')
        
        self.configure(
            bg=self.default_bg,
            fg=self.default_fg,
            relief='flat',
            font=('Segoe UI', 10, 'bold'),
            padx=20,
            pady=10,
            cursor='hand2',
            borderwidth=0
        )
        self.bind('<Enter>', self.on_enter)
        self.bind('<Leave>', self.on_leave)
        
    def on_enter(self, e):
        self.configure(bg=self.hover_bg)
        
    def on_leave(self, e):
        self.configure(bg=self.default_bg)
    
    def update_theme(self, colors):
        self.default_bg = colors['secondary']
        self.hover_bg = colors['hover']
        self.configure(bg=self.default_bg)

class APIKeyManager:
    @staticmethod
    def get_api_key():
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            try:
                with open("api_key.txt", "r") as f:
                    api_key = f.read().strip()
                    os.environ["GROQ_API_KEY"] = api_key
            except:
                pass
        return api_key
    
    @staticmethod
    def save_api_key(api_key):
        try:
            with open("api_key.txt", "w") as f:
                f.write(api_key)
            os.environ["GROQ_API_KEY"] = api_key
            return True
        except:
            return False

class InterviewApp(tk.Tk):
    def __init__(self):
        super().__init__()
        
        self.theme_manager = ThemeManager()
        self.colors = self.theme_manager.get_colors()
        
        self.title(f"{APP_NAME} v{VERSION}")
        self.geometry("1100x800")
        self.minsize(900, 700)
        self.configure(bg=self.colors['background'])
        
        # State variables
        self.candidates = []
        self.current_candidate = None
        self.current_candidate_index = -1
        self.session_id = None
        self.feedback = None
        self.messages = []
        self.interview_active = False
        self.api_key_set = False
        self.is_dark_mode = False
        self.waiting_for_response = False
        self.message_count = 0
        
        self.candidate_sessions = {}
        
        # Widget references
        self.candidate_listbox = None
        self.search_var = None
        self.detail_widgets = []
        self.start_btn = None
        self.load_btn = None
        self.error_label = None
        self.candidate_count = None
        self.details_frame = None
        self.placeholder_label = None
        
        # Interview widgets
        self.interview_candidate_label = None
        self.interview_status = None
        self.chat_display = None
        self.chat_frame = None
        self.message_entry = None
        self.send_btn = None
        self.progress_bar = None
        self.results_btn_frame = None
        self.view_results_btn = None
        self.back_btn = None
        self.input_frame = None
        self.input_label = None
        self.chat_container = None
        self.canvas = None
        self.scrollable_frame = None
        
        # Results widgets
        self.summary_label = None
        self.strengths_label = None
        self.gaps_label = None
        self.next_label = None
        self.charts_frame = None
        
        # Build UI
        self._setup_styles()
        self._build_header()
        self._build_main_container()
        self._build_welcome_screen()
        self._build_interview_screen()
        self._build_results_screen()
        
        self.show_screen('welcome')
        self.after(100, self._check_api_key)
        self.after(100, self._auto_load_candidates)
        self.protocol("WM_DELETE_WINDOW", self._on_closing)
    
    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure(
            'Custom.TCombobox',
            fieldbackground='white',
            background='white',
            foreground=self.colors['text'],
            borderwidth=1,
            arrowsize=12
        )
        style.configure(
            'Custom.Horizontal.TProgressbar',
            background=self.colors['secondary'],
            troughcolor=self.colors['background'],
            borderwidth=0,
            thickness=6
        )
    
    def _update_theme(self):
        self.colors = self.theme_manager.get_colors()
        self.configure(bg=self.colors['background'])
        
        # Update header
        self.header.configure(bg=self.colors['primary'])
        for widget in self.header.winfo_children():
            if isinstance(widget, tk.Frame):
                widget.configure(bg=self.colors['primary'])
        
        # Update main container
        self.main_container.configure(bg=self.colors['background'])
        
        # Update welcome frame
        if hasattr(self, 'welcome_frame'):
            self.welcome_frame.configure(bg=self.colors['background'])
        
        # Update interview frame
        if hasattr(self, 'interview_frame'):
            self.interview_frame.configure(bg=self.colors['background'])
            
            if hasattr(self, 'chat_container') and self.chat_container:
                self.chat_container.configure(bg=self.colors['chat_bg'])
            
            if hasattr(self, 'scrollable_frame') and self.scrollable_frame:
                self.scrollable_frame.configure(bg=self.colors['chat_bg'])
            
            if hasattr(self, 'message_entry') and self.message_entry:
                self.message_entry.configure(
                    bg=self.colors['input_bg'],
                    fg=self.colors['text'],
                    insertbackground=self.colors['text']
                )
            
            if hasattr(self, 'input_label') and self.input_label:
                self.input_label.configure(bg=self.colors['background'], fg=self.colors['text_secondary'])
            
            if hasattr(self, 'input_frame') and self.input_frame:
                self.input_frame.configure(bg=self.colors['background'])
        
        # Update results frame
        if hasattr(self, 'results_frame'):
            self.results_frame.configure(bg=self.colors['background'])
        
        # Update status
        self.status_dot.configure(bg=self.colors['primary'])
        self.status_label.configure(bg=self.colors['primary'])
        
        # Update theme button
        if hasattr(self, 'theme_btn'):
            self.theme_btn.configure(text="🌙 Dark" if not self.is_dark_mode else "☀️ Light")
        
        # Re-render chat messages with new theme
        self._refresh_chat_display()
    
    def _refresh_chat_display(self):
        """Refresh chat messages with new theme colors"""
        if hasattr(self, 'scrollable_frame') and self.scrollable_frame:
            # Clear all chat messages
            for widget in self.scrollable_frame.winfo_children():
                widget.destroy()
            
            # Re-display messages
            for msg in self.messages:
                self._display_message(msg['sender'], msg['text'], msg['time'])
    
    def _toggle_theme(self):
        self.theme_manager.toggle()
        self.is_dark_mode = not self.is_dark_mode
        self._update_theme()
    
    def _build_header(self):
        self.header = tk.Frame(self, bg=self.colors['primary'], height=70)
        self.header.pack(fill='x', side='top')
        self.header.pack_propagate(False)
        
        title_frame = tk.Frame(self.header, bg=self.colors['primary'])
        title_frame.pack(side='left', padx=20, pady=15)
        
        tk.Label(
            title_frame,
            text="🤖 AI Interview Agent",
            font=('Segoe UI', 18, 'bold'),
            fg='white',
            bg=self.colors['primary']
        ).pack(side='left')
        
        tk.Label(
            title_frame,
            text="Technical Interview Simulator",
            font=('Segoe UI', 10),
            fg=self.colors['border'],
            bg=self.colors['primary']
        ).pack(side='left', padx=(10, 0))
        
        control_frame = tk.Frame(self.header, bg=self.colors['primary'])
        control_frame.pack(side='right', padx=20)
        
        self.theme_btn = ModernButton(
            control_frame,
            text="🌙 Dark",
            command=self._toggle_theme,
            bg=self.colors['secondary'],
            hover_bg=self.colors['hover'],
            padx=15,
            pady=5,
            font=('Segoe UI', 9, 'bold'),
            theme_manager=self.theme_manager
        )
        self.theme_btn.pack(side='right', padx=(0, 10))
        
        self.status_frame = tk.Frame(control_frame, bg=self.colors['primary'])
        self.status_frame.pack(side='right')
        
        self.status_dot = tk.Label(
            self.status_frame,
            text="●",
            font=('Segoe UI', 14),
            fg=self.colors['warning'],
            bg=self.colors['primary']
        )
        self.status_dot.pack(side='left')
        
        self.status_label = tk.Label(
            self.status_frame,
            text="Ready",
            font=('Segoe UI', 10),
            fg='white',
            bg=self.colors['primary']
        )
        self.status_label.pack(side='left', padx=(5, 0))
    
    def set_status(self, text, color=None):
        self.status_label.config(text=text)
        if color:
            self.status_dot.config(fg=color)
    
    def _build_main_container(self):
        self.main_container = tk.Frame(self, bg=self.colors['background'])
        self.main_container.pack(fill='both', expand=True, padx=20, pady=20)
    
    def show_screen(self, screen_name):
        if hasattr(self, 'welcome_frame'):
            self.welcome_frame.pack_forget()
        if hasattr(self, 'interview_frame'):
            self.interview_frame.pack_forget()
        if hasattr(self, 'results_frame'):
            self.results_frame.pack_forget()
        
        if screen_name == 'welcome':
            self.welcome_frame.pack(fill='both', expand=True)
        elif screen_name == 'interview':
            self.interview_frame.pack(fill='both', expand=True)
            if hasattr(self, 'message_entry') and self.message_entry:
                self.message_entry.focus_set()
        elif screen_name == 'results':
            self.results_frame.pack(fill='both', expand=True)
    
    def _check_api_key(self):
        api_key = APIKeyManager.get_api_key()
        if api_key:
            self.api_key_set = True
            self.set_status("API Key: OK", self.colors['success'])
            return True
        else:
            self.set_status("API Key: Missing", self.colors['accent'])
            self.after(500, self._show_api_key_dialog)
            return False
    
    def _show_api_key_dialog(self):
        dialog = tk.Toplevel(self)
        dialog.title("API Key Required")
        dialog.geometry("500x350")
        dialog.configure(bg=self.colors['surface'])
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (500 // 2)
        y = (dialog.winfo_screenheight() // 2) - (350 // 2)
        dialog.geometry(f"+{x}+{y}")
        
        main_frame = tk.Frame(dialog, bg=self.colors['surface'])
        main_frame.pack(fill='both', expand=True, padx=30, pady=20)
        
        tk.Label(
            main_frame,
            text="🔑 Groq API Key Required",
            font=('Segoe UI', 16, 'bold'),
            bg=self.colors['surface'],
            fg=self.colors['text']
        ).pack(pady=(0, 10))
        
        tk.Label(
            main_frame,
            text="Please enter your Groq API key to use the AI Interview Agent.\n\n"
                 "Get a free key at: https://console.groq.com",
            font=('Segoe UI', 10),
            bg=self.colors['surface'],
            fg=self.colors['text_secondary'],
            justify='center'
        ).pack(pady=(0, 15))
        
        tk.Label(
            main_frame,
            text="API Key:",
            font=('Segoe UI', 10, 'bold'),
            bg=self.colors['surface'],
            fg=self.colors['text']
        ).pack(anchor='w')
        
        api_entry = tk.Entry(
            main_frame,
            font=('Segoe UI', 10),
            show='*',
            width=50
        )
        api_entry.pack(fill='x', pady=(5, 15))
        api_entry.focus()
        
        btn_frame = tk.Frame(main_frame, bg=self.colors['surface'])
        btn_frame.pack(pady=10)
        
        def on_save():
            api_key = api_entry.get().strip()
            if api_key:
                if APIKeyManager.save_api_key(api_key):
                    self.api_key_set = True
                    self.set_status("API Key: OK", self.colors['success'])
                    dialog.destroy()
                    messagebox.showinfo("Success", "API key saved successfully!")
                    if self.current_candidate and hasattr(self, 'start_btn'):
                        self.start_btn.configure(state='normal')
                else:
                    messagebox.showerror("Error", "Failed to save API key.")
            else:
                messagebox.showwarning("Empty", "Please enter your API key.")
        
        def on_skip():
            dialog.destroy()
        
        ModernButton(
            btn_frame,
            text="✅ Save & Continue",
            command=on_save,
            bg=self.colors['success'],
            hover_bg='#219A52',
            padx=20,
            pady=8,
            theme_manager=self.theme_manager
        ).pack(side='left', padx=5)
        
        ModernButton(
            btn_frame,
            text="🔗 Get API Key",
            command=lambda: webbrowser.open("https://console.groq.com"),
            bg=self.colors['secondary'],
            hover_bg=self.colors['hover'],
            padx=20,
            pady=8,
            theme_manager=self.theme_manager
        ).pack(side='left', padx=5)
        
        ModernButton(
            btn_frame,
            text="Skip",
            command=on_skip,
            bg=self.colors['text_secondary'],
            hover_bg='#6B7B8D',
            padx=20,
            pady=8,
            theme_manager=self.theme_manager
        ).pack(side='left', padx=5)
        
        api_entry.bind('<Return>', lambda e: on_save())
    
    def _build_welcome_screen(self):
        self.welcome_frame = tk.Frame(self.main_container, bg=self.colors['background'])
        
        header_frame = tk.Frame(self.welcome_frame, bg=self.colors['background'])
        header_frame.pack(fill='x', pady=(0, 20))
        
        tk.Label(
            header_frame,
            text="Start an Interview",
            font=('Segoe UI', 24, 'bold'),
            fg=self.colors['text'],
            bg=self.colors['background']
        ).pack(anchor='w')
        
        tk.Label(
            header_frame,
            text="Select a candidate from the list below to begin the technical interview process.",
            font=('Segoe UI', 11),
            fg=self.colors['text_secondary'],
            bg=self.colors['background']
        ).pack(anchor='w', pady=(5, 0))
        
        content_frame = tk.Frame(self.welcome_frame, bg=self.colors['background'])
        content_frame.pack(fill='both', expand=True)
        
        # Left panel
        left_panel = tk.Frame(content_frame, bg=self.colors['surface'], relief='solid', bd=1)
        left_panel.pack(side='left', fill='both', expand=True, padx=(0, 10))
        
        list_header = tk.Frame(left_panel, bg=self.colors['primary'], height=40)
        list_header.pack(fill='x')
        list_header.pack_propagate(False)
        
        tk.Label(
            list_header,
            text="📋 Available Candidates",
            font=('Segoe UI', 12, 'bold'),
            fg='white',
            bg=self.colors['primary']
        ).pack(side='left', padx=15, pady=8)
        
        self.candidate_count = tk.Label(
            list_header,
            text="0 candidates",
            font=('Segoe UI', 9),
            fg=self.colors['border'],
            bg=self.colors['primary']
        )
        self.candidate_count.pack(side='right', padx=15)
        
        search_frame = tk.Frame(left_panel, bg=self.colors['background'], height=40)
        search_frame.pack(fill='x', padx=10, pady=10)
        search_frame.pack_propagate(False)
        
        tk.Label(
            search_frame,
            text="🔍",
            font=('Segoe UI', 12),
            bg=self.colors['background']
        ).pack(side='left', padx=(0, 5))
        
        self.search_var = tk.StringVar()
        self.search_var.trace('w', lambda *args: self._filter_candidates())
        
        search_entry = tk.Entry(
            search_frame,
            textvariable=self.search_var,
            font=('Segoe UI', 10),
            relief='solid',
            bd=1,
            bg=self.colors['input_bg'],
            fg=self.colors['text']
        )
        search_entry.pack(side='left', fill='x', expand=True)
        search_entry.insert(0, "Search candidates...")
        search_entry.bind('<FocusIn>', lambda e: search_entry.delete(0, 'end') if search_entry.get() == "Search candidates..." else None)
        search_entry.bind('<FocusOut>', lambda e: search_entry.insert(0, "Search candidates...") if not search_entry.get() else None)
        
        list_container = tk.Frame(left_panel, bg=self.colors['background'])
        list_container.pack(fill='both', expand=True, padx=10, pady=(0, 10))
        
        self.candidate_listbox = tk.Listbox(
            list_container,
            font=('Segoe UI', 10),
            bg=self.colors['surface'],
            fg=self.colors['text'],
            selectbackground=self.colors['secondary'],
            selectforeground='white',
            relief='flat',
            bd=1,
            height=12,
            activestyle='none'
        )
        
        scrollbar = tk.Scrollbar(list_container, orient='vertical', command=self.candidate_listbox.yview)
        self.candidate_listbox.configure(yscrollcommand=scrollbar.set)
        self.candidate_listbox.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        self.candidate_listbox.bind('<<ListboxSelect>>', self._on_candidate_select)
        
        # Right panel
        right_panel = tk.Frame(content_frame, bg=self.colors['surface'], relief='solid', bd=1)
        right_panel.pack(side='right', fill='both', expand=True, padx=(10, 0))
        
        details_header = tk.Frame(right_panel, bg=self.colors['primary'], height=40)
        details_header.pack(fill='x')
        details_header.pack_propagate(False)
        
        tk.Label(
            details_header,
            text="👤 Candidate Details",
            font=('Segoe UI', 12, 'bold'),
            fg='white',
            bg=self.colors['primary']
        ).pack(side='left', padx=15, pady=8)
        
        self.details_frame = tk.Frame(right_panel, bg=self.colors['surface'], padx=20, pady=20)
        self.details_frame.pack(fill='both', expand=True)
        
        self.placeholder_label = tk.Label(
            self.details_frame,
            text="Select a candidate to view details",
            font=('Segoe UI', 12),
            fg=self.colors['text_secondary'],
            bg=self.colors['surface']
        )
        self.placeholder_label.pack(expand=True)
        
        self.detail_widgets = []
        
        action_frame = tk.Frame(self.welcome_frame, bg=self.colors['background'])
        action_frame.pack(fill='x', pady=(20, 0))
        
        self.load_btn = ModernButton(
            action_frame,
            text="📂 Load Candidates",
            command=self._load_candidates_dialog,
            bg=self.colors['secondary'],
            hover_bg=self.colors['hover'],
            theme_manager=self.theme_manager
        )
        self.load_btn.pack(side='left', padx=(0, 10))
        
        self.start_btn = ModernButton(
            action_frame,
            text="▶ Start Interview",
            command=self._start_interview,
            bg=self.colors['success'],
            hover_bg='#219A52',
            theme_manager=self.theme_manager,
            state='disabled'
        )
        self.start_btn.pack(side='left')
        
        self.error_label = tk.Label(
            self.welcome_frame,
            text="",
            font=('Segoe UI', 10),
            fg=self.colors['accent'],
            bg=self.colors['background']
        )
        self.error_label.pack(pady=(10, 0))
    
    def _filter_candidates(self):
        listbox = getattr(self, 'candidate_listbox', None)
        if not listbox:
            return
        query = self.search_var.get().lower() if getattr(self, 'search_var', None) else ""
        listbox.delete(0, tk.END)
        
        for candidate in self.candidates:
            name = candidate['member']['name'].lower()
            role = candidate['member']['jobRole'].lower()
            if query in name or query in role or query == "search candidates...":
                display_name = f"{candidate['member']['name']} — {candidate['member']['jobRole']}"
                listbox.insert(tk.END, display_name)
    
    def _on_candidate_select(self, event):
        if not self.candidate_listbox:
            return
        selection = self.candidate_listbox.curselection()
        if not selection:
            return
        
        idx = selection[0]
        if idx >= len(self.candidates):
            return
        
        if self.current_candidate_index != idx:
            self.current_candidate_index = idx
            if idx in self.candidate_sessions:
                del self.candidate_sessions[idx]
        
        self.current_candidate = self.candidates[idx]
        if self.start_btn:
            self.start_btn.configure(state='normal' if self.api_key_set else 'disabled')
        self._update_candidate_details(idx)
    
    def _update_candidate_details(self, idx):
        if not self.details_frame:
            return
        candidate = self.candidates[idx]
        member = candidate['member']
        
        for widget in self.detail_widgets:
            widget.destroy()
        self.detail_widgets.clear()
        if self.placeholder_label:
            self.placeholder_label.pack_forget()

        experience = member.get('yearsExperience', member.get('experience', 'Not specified'))

        details = [
            ("Name", member['name']),
            ("Role", member['jobRole']),
            ("Experience", experience),
            ("Skills", ", ".join(member.get('skills', ['Not specified'])[:5])),
            ("Location", member.get('location', 'Not specified')),
            ("Email", member.get('email', 'Not specified'))
        ]
        
        for label, value in details:
            row_frame = tk.Frame(self.details_frame, bg=self.colors['surface'])
            row_frame.pack(fill='x', pady=3)
            self.detail_widgets.append(row_frame)
            
            label_widget = tk.Label(
                row_frame,
                text=f"{label}:",
                font=('Segoe UI', 9, 'bold'),
                fg=self.colors['text_secondary'],
                bg=self.colors['surface'],
                width=15,
                anchor='w'
            )
            label_widget.pack(side='left')
            self.detail_widgets.append(label_widget)
            
            value_widget = tk.Label(
                row_frame,
                text=str(value),
                font=('Segoe UI', 10),
                fg=self.colors['text'],
                bg=self.colors['surface'],
                wraplength=200,
                justify='left'
            )
            value_widget.pack(side='left', fill='x', expand=True)
            self.detail_widgets.append(value_widget)
        
        separator = tk.Frame(self.details_frame, bg=self.colors['border'], height=1)
        separator.pack(fill='x', pady=8)
        self.detail_widgets.append(separator)
        
        description = candidate.get('description', 'No additional information available.')
        desc_label = tk.Label(
            self.details_frame,
            text=description,
            font=('Segoe UI', 10),
            fg=self.colors['text'],
            bg=self.colors['surface'],
            wraplength=250,
            justify='left'
        )
        desc_label.pack(anchor='w', pady=(5, 0))
        self.detail_widgets.append(desc_label)
    
    def _start_interview(self):
        if not self.current_candidate:
            messagebox.showwarning("No Candidate", "Please select a candidate first.")
            return
        
        if not self.api_key_set:
            messagebox.showwarning("API Key Missing", "Please set your Groq API key first.")
            self._show_api_key_dialog()
            return
        
        if not AGENT_AVAILABLE:
            messagebox.showerror(
                "Agent Not Available",
                "The interview agent (main.py) could not be loaded."
            )
            return
        
        candidate_id = self.current_candidate_index
        if candidate_id in self.candidate_sessions:
            del self.candidate_sessions[candidate_id]
        
        self.session_id = str(uuid.uuid4())
        self.candidate_sessions[candidate_id] = self.session_id
        self.messages = []
        self.feedback = None
        self.interview_active = True
        self.waiting_for_response = False
        self.message_count = 0
        
        # Clear chat display
        if hasattr(self, 'scrollable_frame') and self.scrollable_frame:
            for widget in self.scrollable_frame.winfo_children():
                widget.destroy()
        
        self.show_screen('interview')
        if self.interview_candidate_label:
            self.interview_candidate_label.config(
                text=f"Interviewing: {self.current_candidate['member']['name']}"
            )
        
        # Make sure input area is visible
        if self.input_frame:
            self.input_frame.pack(fill='x', pady=(10, 0))
            self.input_frame.lift()
        
        if self.send_btn:
            self.send_btn.configure(state='disabled')
        if self.message_entry:
            self.message_entry.configure(state='normal')
            self.message_entry.delete("1.0", tk.END)
            self.message_entry.focus_set()
        
        self.set_status("Starting interview...", self.colors['warning'])
        
        if self.progress_bar:
            self.progress_bar.pack(fill='x', pady=(0, 5))
            self.progress_bar.start(10)
        
        threading.Thread(target=self._start_interview_worker, daemon=True).start()
    
    def _start_interview_worker(self):
        try:
            response = call_agent(agent._start_session, self.session_id, self.current_candidate)
            self.after(0, self._on_interview_started, response)
        except Exception as e:
            self.after(0, self._on_interview_error, str(e))
    
    def _on_interview_started(self, response):
        if self.progress_bar:
            self.progress_bar.stop()
            self.progress_bar.pack_forget()
        
        self._add_message("ai", response.reply)
        self.waiting_for_response = True
        
        # Enable input for the candidate
        if self.send_btn:
            self.send_btn.configure(state='normal')
        if self.message_entry:
            self.message_entry.configure(state='normal')
            self.message_entry.focus_set()
        
        if self.input_label:
            self.input_label.config(text="✏️ Type your answer here:")
        
        self.set_status("Waiting for your response...", self.colors['success'])
        self.interview_active = True
    
    def _on_interview_error(self, error_msg):
        if self.progress_bar:
            self.progress_bar.stop()
            self.progress_bar.pack_forget()
        self.interview_active = False
        self.waiting_for_response = False
        
        messagebox.showerror("Interview Error", f"Failed to start interview:\n{error_msg}")
        self.set_status("Error", self.colors['accent'])
        if self.send_btn:
            self.send_btn.configure(state='disabled')
        if self.message_entry:
            self.message_entry.configure(state='disabled')
    
    def _build_interview_screen(self):
        self.interview_frame = tk.Frame(self.main_container, bg=self.colors['background'])
        
        # Chat Header
        chat_header = tk.Frame(self.interview_frame, bg=self.colors['surface'], relief='solid', bd=1, height=60)
        chat_header.pack(fill='x')
        chat_header.pack_propagate(False)
        
        self.back_btn = ModernButton(
            chat_header,
            text="← Back",
            command=self._back_to_welcome,
            bg=self.colors['text_secondary'],
            hover_bg='#6B7B8D',
            padx=15,
            pady=5,
            font=('Segoe UI', 9, 'bold'),
            theme_manager=self.theme_manager
        )
        self.back_btn.pack(side='left', padx=(15, 10))
        
        self.interview_candidate_label = tk.Label(
            chat_header,
            text="Interviewing: Candidate Name",
            font=('Segoe UI', 12, 'bold'),
            fg=self.colors['text'],
            bg=self.colors['surface']
        )
        self.interview_candidate_label.pack(side='left')
        
        self.interview_status = tk.Label(
            chat_header,
            text="● Active",
            font=('Segoe UI', 9),
            fg=self.colors['success'],
            bg=self.colors['surface']
        )
        self.interview_status.pack(side='right', padx=15)
        
        # ============================================
        # CHAT DISPLAY - Like ChatGPT/DeepSeek
        # ============================================
        self.chat_container = tk.Frame(self.interview_frame, bg=self.colors['chat_bg'])
        self.chat_container.pack(fill='both', expand=True, pady=(10, 0))
        
        # Canvas with scrollbar for chat messages
        self.canvas = tk.Canvas(
            self.chat_container,
            bg=self.colors['chat_bg'],
            highlightthickness=0
        )
        scrollbar = tk.Scrollbar(
            self.chat_container,
            orient='vertical',
            command=self.canvas.yview
        )
        
        self.scrollable_frame = tk.Frame(
            self.canvas,
            bg=self.colors['chat_bg']
        )
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        self.canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Mouse wheel scrolling
        def _on_mousewheel(event):
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        self.canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        # ============================================
        # INPUT AREA - Like ChatGPT
        # ============================================
        self.input_frame = tk.Frame(self.interview_frame, bg=self.colors['background'])
        self.input_frame.pack(fill='x', pady=(10, 0))
        
        # Input box frame
        input_box_frame = tk.Frame(self.input_frame, bg=self.colors['background'])
        input_box_frame.pack(fill='x', padx=10)
        
        # Text entry for candidate responses
        self.message_entry = tk.Text(
            input_box_frame,
            height=3,
            font=('Segoe UI', 11),
            wrap='word',
            relief='solid',
            bd=2,
            padx=15,
            pady=12,
            bg=self.colors['input_bg'],
            fg=self.colors['text'],
            insertbackground=self.colors['text'],
            highlightthickness=1,
            highlightcolor=self.colors['secondary'],
            highlightbackground=self.colors['input_border']
        )
        self.message_entry.pack(side='left', fill='x', expand=True, padx=(0, 10))
        
        # Bind Enter key to send
        self.message_entry.bind('<Return>', self._on_enter_pressed)
        self.message_entry.bind('<Shift-Return>', lambda e: None)
        
        # Send button
        self.send_btn = ModernButton(
            input_box_frame,
            text="Send ➤",
            command=self._send_message,
            bg=self.colors['secondary'],
            hover_bg=self.colors['hover'],
            padx=25,
            pady=15,
            theme_manager=self.theme_manager
        )
        self.send_btn.pack(side='right', fill='y')
        
        # Progress bar
        self.progress_frame = tk.Frame(self.interview_frame, bg=self.colors['background'])
        self.progress_frame.pack(fill='x', pady=(10, 0))
        
        self.progress_bar = ttk.Progressbar(
            self.progress_frame,
            style='Custom.Horizontal.TProgressbar',
            length=100,
            mode='indeterminate'
        )
        
        # Results button (hidden initially)
        self.results_btn_frame = tk.Frame(self.interview_frame, bg=self.colors['background'])
        self.view_results_btn = ModernButton(
            self.results_btn_frame,
            text="📊 View Results",
            command=self._show_results,
            bg=self.colors['success'],
            hover_bg='#219A52',
            padx=30,
            pady=10,
            theme_manager=self.theme_manager
        )
    
    def _on_enter_pressed(self, event):
        if not event.state & 0x1:
            self._send_message()
            return "break"
    
    def _display_message(self, sender, text, time):
        """Display a message in the chat with proper styling"""
        if not self.scrollable_frame:
            return
        
        # Create message bubble
        ChatMessage(self.scrollable_frame, sender, text, time, self.colors)
        
        # Scroll to bottom
        self.canvas.yview_moveto(1.0)
        self.update_idletasks()
    
    def _add_message(self, sender, text):
        """Add a message to the chat"""
        time = datetime.now().strftime("%H:%M")
        
        # Store message
        self.messages.append({
            'sender': sender,
            'text': text,
            'time': time
        })
        
        # Display message
        self._display_message(sender, text, time)
        
        # If message is from AI, enable input
        if sender == 'ai':
            self.waiting_for_response = True
            if self.send_btn:
                self.send_btn.configure(state='normal')
            if self.message_entry:
                self.message_entry.configure(state='normal')
                self.message_entry.focus_set()
            if self.input_label:
                self.input_label.config(text="✏️ Type your answer here:")
            self.set_status("Waiting for your response...", self.colors['success'])
    
    def _send_message(self):
        if not self.interview_active:
            messagebox.showinfo("Interview Ended", "This interview has ended.")
            return
        
        if not self.message_entry:
            return
        
        message = self.message_entry.get("1.0", tk.END).strip()
        if not message:
            return
        
        # Clear input
        self.message_entry.delete("1.0", tk.END)
        
        # Add user message to chat
        self._add_message("user", message)
        self.waiting_for_response = False
        
        # Disable input while processing
        if self.send_btn:
            self.send_btn.configure(state='disabled')
        if self.message_entry:
            self.message_entry.configure(state='disabled')
        
        self.set_status("Processing your answer...", self.colors['warning'])
        
        # Send in background thread
        threading.Thread(target=self._send_message_worker, args=(message,), daemon=True).start()
    
    def _send_message_worker(self, message):
        try:
            response = call_agent(agent._continue_session, self.session_id, message)
            self.after(0, self._on_message_response, response)
        except Exception as e:
            self.after(0, self._on_interview_error, str(e))
    
    def _on_message_response(self, response):
        self._add_message("ai", response.reply)
        
        if response.done:
            # Interview is complete
            self.interview_active = False
            self.feedback = response.feedback
            self.waiting_for_response = False
            
            if self.send_btn:
                self.send_btn.configure(state='disabled')
            if self.message_entry:
                self.message_entry.configure(state='disabled')
            
            self.set_status("Interview completed!", self.colors['success'])
            
            # Show results button
            if self.results_btn_frame and self.view_results_btn:
                self.results_btn_frame.pack(fill='x', pady=(10, 0))
                self.view_results_btn.pack()
            
            self._add_message("system", "✅ Interview complete! Click 'View Results' to see the evaluation.")
    
    def _back_to_welcome(self):
        if self.interview_active and self.waiting_for_response:
            if not messagebox.askyesno("Confirm", "The interview is still in progress. Are you sure you want to leave?"):
                return
        
        self.interview_active = False
        self.waiting_for_response = False
        
        if self.progress_bar:
            self.progress_bar.stop()
            self.progress_bar.pack_forget()
        if self.results_btn_frame:
            self.results_btn_frame.pack_forget()
        
        # Clear chat
        if hasattr(self, 'scrollable_frame') and self.scrollable_frame:
            for widget in self.scrollable_frame.winfo_children():
                widget.destroy()
            self.messages = []
        
        self.show_screen('welcome')
        self.set_status("Ready", self.colors['warning'])
    
    def _build_results_screen(self):
        self.results_frame = tk.Frame(self.main_container, bg=self.colors['background'])
        
        results_header = tk.Frame(self.results_frame, bg=self.colors['surface'], relief='solid', bd=1, height=60)
        results_header.pack(fill='x')
        results_header.pack_propagate(False)
        
        back_btn = ModernButton(
            results_header,
            text="← Back to Interview",
            command=self._back_to_interview,
            bg=self.colors['text_secondary'],
            hover_bg='#6B7B8D',
            padx=15,
            pady=5,
            font=('Segoe UI', 9, 'bold'),
            theme_manager=self.theme_manager
        )
        back_btn.pack(side='left', padx=(15, 10))
        
        tk.Label(
            results_header,
            text="📊 Interview Results",
            font=('Segoe UI', 14, 'bold'),
            fg=self.colors['text'],
            bg=self.colors['surface']
        ).pack(side='left')
        
        results_container = tk.Frame(self.results_frame, bg=self.colors['background'])
        results_container.pack(fill='both', expand=True, pady=(10, 0))
        
        canvas = tk.Canvas(results_container, bg=self.colors['background'], highlightthickness=0)
        scrollbar = tk.Scrollbar(results_container, orient='vertical', command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=self.colors['background'])
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        # Summary section
        self.summary_frame = tk.Frame(scrollable_frame, bg=self.colors['surface'], relief='solid', bd=1)
        self.summary_frame.pack(fill='x', padx=20, pady=(0, 15))
        
        self.summary_label = tk.Label(
            self.summary_frame,
            text="",
            font=('Segoe UI', 11),
            fg=self.colors['text'],
            bg=self.colors['surface'],
            wraplength=800,
            justify='left',
            padx=20,
            pady=15
        )
        self.summary_label.pack(fill='x')
        
        self.charts_frame = tk.Frame(scrollable_frame, bg=self.colors['background'])
        self.charts_frame.pack(fill='x', pady=(0, 15))
        
        self.lists_frame = tk.Frame(scrollable_frame, bg=self.colors['background'])
        self.lists_frame.pack(fill='x')
        
        columns_frame = tk.Frame(self.lists_frame, bg=self.colors['background'])
        columns_frame.pack(fill='x')
        
        # Strengths
        strengths_frame = tk.Frame(columns_frame, bg=self.colors['surface'], relief='solid', bd=1)
        strengths_frame.pack(side='left', fill='both', expand=True, padx=(0, 5))
        
        tk.Label(
            strengths_frame,
            text="✅ Strengths",
            font=('Segoe UI', 12, 'bold'),
            fg=self.colors['success'],
            bg=self.colors['surface'],
            padx=15,
            pady=10
        ).pack(anchor='w')
        
        self.strengths_label = tk.Label(
            strengths_frame,
            text="",
            font=('Segoe UI', 10),
            fg=self.colors['text'],
            bg=self.colors['surface'],
            justify='left',
            anchor='w',
            padx=15,
        )
        self.strengths_label.pack(anchor='w', pady=(0, 15))
        
        # Gaps
        gaps_frame = tk.Frame(columns_frame, bg=self.colors['surface'], relief='solid', bd=1)
        gaps_frame.pack(side='left', fill='both', expand=True, padx=5)
        
        tk.Label(
            gaps_frame,
            text="⚠️ Areas for Improvement",
            font=('Segoe UI', 12, 'bold'),
            fg=self.colors['accent'],
            bg=self.colors['surface'],
            padx=15,
            pady=10
        ).pack(anchor='w')
        
        self.gaps_label = tk.Label(
            gaps_frame,
            text="",
            font=('Segoe UI', 10),
            fg=self.colors['text'],
            bg=self.colors['surface'],
            justify='left',
            anchor='w',
            padx=15,
        )
        self.gaps_label.pack(anchor='w', pady=(0, 15))
        
        # Next Steps
        next_frame = tk.Frame(columns_frame, bg=self.colors['surface'], relief='solid', bd=1)
        next_frame.pack(side='left', fill='both', expand=True, padx=(5, 0))
        
        tk.Label(
            next_frame,
            text="🎯 Next Steps",
            font=('Segoe UI', 12, 'bold'),
            fg=self.colors['secondary'],
            bg=self.colors['surface'],
            padx=15,
            pady=10
        ).pack(anchor='w')
        
        self.next_label = tk.Label(
            next_frame,
            text="",
            font=('Segoe UI', 10),
            fg=self.colors['text'],
            bg=self.colors['surface'],
            justify='left',
            anchor='w',
            padx=15,
        )
        self.next_label.pack(anchor='w', pady=(0, 15))
    
    def _show_results(self):
        if not self.feedback:
            messagebox.showinfo("No Results", "No interview results available yet.")
            return
        
        self.show_screen('results')
        self._render_results()
    
    def _back_to_interview(self):
        self.show_screen('interview')
    
    def _render_results(self):
        if not MATPLOTLIB_AVAILABLE:
            messagebox.showinfo(
                "Matplotlib Not Available",
                "Please install matplotlib to view charts:\npip install matplotlib"
            )
            return
        
        feedback = self.feedback
        
        self.summary_label.config(text=feedback.summary)
        self.strengths_label.config(text="\n".join(f"• {s}" for s in feedback.strengths) if feedback.strengths else "No strengths identified")
        self.gaps_label.config(text="\n".join(f"• {g}" for g in feedback.gaps) if feedback.gaps else "No gaps identified")
        self.next_label.config(text="\n".join(f"• {n}" for n in feedback.next) if feedback.next else "No next steps identified")
        
        for widget in self.charts_frame.winfo_children():
            widget.destroy()
        
        fig = Figure(figsize=(8, 4), dpi=100, facecolor=self.colors['background'])
        
        # Chart 1: Strengths vs Gaps
        ax1 = fig.add_subplot(121)
        categories = ['Strengths', 'Gaps']
        values = [feedback.strengthsCount, feedback.gapsCount]
        colors = [self.colors['success'], self.colors['accent']]
        
        bars = ax1.bar(categories, values, color=colors, edgecolor='white', linewidth=1)
        ax1.set_title('Strengths vs Areas for Improvement', fontsize=10, fontweight='bold', color=self.colors['text'])
        ax1.set_ylabel('Count', fontsize=9, color=self.colors['text'])
        ax1.tick_params(axis='both', labelsize=8, colors=self.colors['text'])
        ax1.set_facecolor(self.colors['background'])
        ax1.grid(axis='y', alpha=0.3)
        ax1.spines['bottom'].set_color(self.colors['border'])
        ax1.spines['left'].set_color(self.colors['border'])
        
        for bar, value in zip(bars, values):
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height,
                    f'{value}', ha='center', va='bottom', fontsize=9, fontweight='bold', color=self.colors['text'])
        
        # Chart 2: Topics covered
        ax2 = fig.add_subplot(122)
        module_names = {
            1: "Environment", 2: "Data", 3: "Embeddings",
            4: "LLM/Prompt", 5: "Chatbot", 6: "Agentic",
            7: "Eval/Deploy", 8: "Production"
        }
        
        topic_counts = {m: 0 for m in module_names.keys()}
        if hasattr(feedback, 'topicsCovered') and feedback.topicsCovered:
            for topic in feedback.topicsCovered:
                if hasattr(topic, 'module') and topic.module in topic_counts:
                    topic_counts[topic.module] += 1
        
        modules = list(module_names.values())
        counts = [topic_counts[m] for m in module_names.keys()]
        
        ax2.barh(modules, counts, color=self.colors['secondary'], edgecolor='white', linewidth=1)
        ax2.set_title('Topics Covered by Module', fontsize=10, fontweight='bold', color=self.colors['text'])
        ax2.set_xlabel('Count', fontsize=9, color=self.colors['text'])
        ax2.tick_params(axis='both', labelsize=7, colors=self.colors['text'])
        ax2.set_facecolor(self.colors['background'])
        ax2.grid(axis='x', alpha=0.3)
        ax2.spines['bottom'].set_color(self.colors['border'])
        ax2.spines['left'].set_color(self.colors['border'])
        
        for i, count in enumerate(counts):
            if count > 0:
                ax2.text(count + 0.1, i, f'{count}', va='center', fontsize=8, color=self.colors['text'])
        
        fig.tight_layout()
        
        canvas = FigureCanvasTkAgg(fig, master=self.charts_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill='both', expand=True, padx=10, pady=10)
    
    def _auto_load_candidates(self):
        if os.path.exists(CANDIDATES_FILE):
            try:
                self._load_candidates(CANDIDATES_FILE)
            except Exception as e:
                print(f"Auto-load error: {e}")
    
    def _load_candidates_dialog(self):
        file_path = filedialog.askopenfilename(
            title="Select candidates file",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if file_path:
            self._load_candidates(file_path)
    
    def _load_candidates(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.candidates = data.get('candidates', [])
            
            self.candidate_listbox.delete(0, tk.END)
            for candidate in self.candidates:
                name = candidate['member']['name']
                role = candidate['member']['jobRole']
                self.candidate_listbox.insert(tk.END, f"{name} — {role}")
            
            self.candidate_count.config(text=f"{len(self.candidates)} candidates")
            self.set_status("Candidates loaded", self.colors['success'])
            
            if self.candidates:
                self.candidate_listbox.selection_set(0)
                self._on_candidate_select(None)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load candidates:\n{str(e)}")
            self.set_status("Error loading candidates", self.colors['accent'])
    
    def _on_closing(self):
        if self.interview_active:
            if not messagebox.askyesno("Confirm Exit", "The interview is still in progress. Are you sure you want to exit?"):
                return
        self.destroy()

if __name__ == "__main__":
    api_key = APIKeyManager.get_api_key()
    if not api_key:
        print("=" * 60)
        print("⚠️  WARNING: GROQ_API_KEY is not set!")
        print("=" * 60)
        print("\nThe application will prompt you to enter your API key.")
        print("Get your free API key at: https://console.groq.com")
        print("=" * 60 + "\n")
    
    app = InterviewApp()
    app.mainloop()