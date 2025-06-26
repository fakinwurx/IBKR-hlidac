# openai_chat_manager.py
import openai
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QThread, pyqtSignal

class OpenAIWorker(QThread):
    """
    A worker thread to handle OpenAI API calls to avoid freezing the UI.
    """
    response_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)

    def __init__(self, prompt, model):
        super().__init__()
        self.prompt = prompt
        self.model = model

    def run(self):
        try:
            # Placeholder for OpenAI API key.
            # In a real application, consider more secure ways to manage API keys.
            # For this example, we assume it's set globally or configured.
            # openai.api_key = 'YOUR_API_KEY'
            
            completion = openai.chat.completions.create(
                model=self.model,
                messages=[
                    # Vylepšená systémová zpráva
                    {"role": "system", "content": "You are a concise and helpful assistant specialized in finance and trading, especially delta-neutral strategies. When provided with position data, **carefully analyze it** and provide **brief, direct insights or actionable suggestions** based on the provided context. Prioritize brevity and actionable information."},
                    # OPRAVA: Změna 'role: user' na 'role": "user"'
                    {"role": "user", "content": self.prompt} # self.prompt (který je full_prompt) je použit zde
                ]
            )
            response_text = completion.choices[0].message.content
            self.response_signal.emit(response_text)
        except Exception as e:
            self.error_signal.emit(f"Chyba při komunikaci s OpenAI: {e}")


class OpenAIChatManager:
    def __init__(self, api_key, chat_log_widget, gpt_output_widget):
        """
        Initializes the OpenAIChatManager.

        Args:
            api_key (str): Your OpenAI API key.
            chat_log_widget (QTextEdit): Reference to the QTextEdit widget for general logs.
            gpt_output_widget (QTextEdit): Reference to the QTextEdit widget to display GPT responses.
        """
        openai.api_key = api_key # Set the API key for the openai library
        self.chat_log = chat_log_widget # For general system messages/logs
        self.gpt_output = gpt_output_widget # For GPT's responses
        self.worker = None # To hold the reference to the worker thread

    def ask_gpt(self, prompt, model):
        """
        Sends a prompt to the OpenAI GPT model and displays the response.
        Uses a separate thread to prevent UI freezing.

        Args:
            prompt (str): The user's query.
            model (str): The OpenAI model to use (e.g., "gpt-4o", "gpt-3.5-turbo").
        """
        if not prompt.strip():
            self.chat_log.append("Prosím, zadejte dotaz.") # Log message to general log
            return

        self.gpt_output.setText("Dotazuji se GPT, prosím čekejte...") # Show status in GPT output
        QApplication.processEvents() # Update UI immediately

        # Create and start the worker thread
        self.worker = OpenAIWorker(prompt, model)
        self.worker.response_signal.connect(self._handle_response)
        self.worker.error_signal.connect(self._handle_error)
        self.worker.start()

    def _handle_response(self, response_text):
        """Callback to handle a successful OpenAI response."""
        self.gpt_output.setText(response_text) # Update GPT output area

    def _handle_error(self, error_message):
        """Callback to handle an error from the OpenAI API call."""
        self.gpt_output.setText(error_message) # Update GPT output area

