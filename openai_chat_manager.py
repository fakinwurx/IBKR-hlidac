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
            # You might need to set it here if not using a global config.
            # openai.api_key = 'YOUR_API_KEY'
            
            completion = openai.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant specialized in finance and trading, especially delta-neutral strategies."},
                    {"role": "user", "content": self.prompt}
                ]
            )
            response_text = completion.choices[0].message.content
            self.response_signal.emit(response_text)
        except Exception as e:
            self.error_signal.emit(f"Chyba při komunikaci s OpenAI: {e}")


class OpenAIChatManager:
    def __init__(self, api_key, chat_output_widget):
        """
        Initializes the OpenAIChatManager.

        Args:
            api_key (str): Your OpenAI API key.
            chat_output_widget (QTextEdit): Reference to the QTextEdit widget
                                            to display responses/errors.
        """
        openai.api_key = api_key # Set the API key for the openai library
        self.chat_output = chat_output_widget
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
            self.chat_output.setText("Prosím, zadejte dotaz.")
            return

        self.chat_output.setText("Dotazuji se GPT, prosím čekejte...")
        QApplication.processEvents() # Update UI immediately

        # Create and start the worker thread
        self.worker = OpenAIWorker(prompt, model)
        self.worker.response_signal.connect(self._handle_response)
        self.worker.error_signal.connect(self._handle_error)
        self.worker.start()

    def _handle_response(self, response_text):
        """Callback to handle a successful OpenAI response."""
        self.chat_output.setText(response_text)

    def _handle_error(self, error_message):
        """Callback to handle an error from the OpenAI API call."""
        self.chat_output.setText(error_message)

