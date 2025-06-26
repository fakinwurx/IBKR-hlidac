# main_app.py
import sys
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QLineEdit, QTextEdit, QComboBox, QHeaderView,
    QMessageBox
)
from PyQt6.QtGui import QColor

# Import the new manager classes and config
from ib_manager import IBManager
from database_manager import DatabaseManager
from openai_chat_manager import OpenAIChatManager
import config

class DeltaNeutralApp(QWidget):
    def __init__(self):
        super().__init__()

        # --- Initialize chat_output early for error messages from managers ---
        self.chat_output = QTextEdit(self)
        self.chat_output.setPlaceholderText("Odpověď GPT se objeví zde.")
        self.chat_output.setReadOnly(True)
        # -------------------------------------------------------------------

        # Initialize Managers, passing chat_output for messaging
        self.ib_manager = IBManager(self.chat_output)
        self.db_manager = DatabaseManager(config.DATABASE_PATH, self.chat_output)
        self.openai_manager = OpenAIChatManager(config.OPENAI_API_KEY, self.chat_output)

        # Setup UI
        self.initUI()

    def initUI(self):
        # Window setup
        self.setWindowTitle('Delta Neutral Strategie a OpenAI Chat')
        self.setGeometry(100, 100, 1000, 600)

        # Main Layout
        main_layout = QHBoxLayout()

        # Left side layout for positions table and details
        left_layout = QVBoxLayout()

        # Upper window with open positions (from DN database - strategy entries)
        self.positions_label = QTextEdit()
        self.positions_label.setReadOnly(True)
        self.positions_label.setMaximumHeight(40)
        self.positions_label.setMinimumHeight(20)
        self.positions_label.setPlainText('Otevřené Pozice (Strategie):')
        self.positions_label.setStyleSheet("""
            QTextEdit {
                background-color: transparent;
                border: none;
                font-size: 12pt;
                font-weight: bold;
            }
        """)
        self.positions_table = QTableWidget()
        self.positions_table.setColumnCount(3)
        self.positions_table.setHorizontalHeaderLabels(['Ticker', 'Datum Vstup', 'Datum Výstup'])
        self.positions_table.cellClicked.connect(self.on_position_click)

        # Bottom window with selected position details
        self.details_label = QLabel('Detaily vybrané pozice:')
        self.details_text = QLabel('Vyberte pozici pro zobrazení detailů.')
        
        # Add summary table for closed positions
        self.summary_label = QLabel('Souhrn PnL uzavřených pozic (z historie obchodů):')
        self.summary_table = QTableWidget()
        self.summary_table.setMaximumHeight(120)

        self.summary_table.setColumnCount(4)
        self.summary_table.setHorizontalHeaderLabels([
            'Symbol', 'Celk. realizovaný PnL', 'Celk. čistá hotovost (Báze Ccy)', 'Celk. FX PnL'
        ])
        header = self.summary_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        
        # Add break-even and current PnL labels ABOVE new live positions table
        self.delta_breakeven_label = QLabel('Break-even (Při otevření strategie): N/A')
        self.current_pnl_label = QLabel('Aktuální PnL (Otevřené pozice z IB): N/A')

        # New table for LIVE IB Open Positions details
        self.ib_live_positions_label = QLabel('Detailní živé pozice z IB:')
        self.ib_live_positions_table = QTableWidget()
        self.ib_live_positions_table.setColumnCount(8)
        self.ib_live_positions_table.setHorizontalHeaderLabels([
            'Symbol', 'Typ', 'Právo', 'Strike', 'Množství', 'Tržní hodnota', 'Prům. cena', 'Nerealizovaný PnL'
        ])
        live_header = self.ib_live_positions_table.horizontalHeader()
        live_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        live_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        live_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        live_header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        live_header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        live_header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        live_header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        live_header.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)

        # Add trade history table
        self.trade_history_label = QLabel('Historie obchodů pro vybraný Ticker:')
        self.trade_history_table = QTableWidget()
        self.trade_history_table.setColumnCount(5) # This will be updated by db_manager
        self.trade_history_table.setHorizontalHeaderLabels([
            'Datum', 'Symbol', 'Množství', 'Realizovaný PnL', 'Čistá Hotovost' # These will also be updated
        ])
        history_header = self.trade_history_table.horizontalHeader()
        history_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        history_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        history_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        history_header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        history_header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)

        # Layout for buttons
        button_layout = QHBoxLayout()

        # Load Button (for DN positions from DB)
        load_dn_strategies_button = QPushButton('Načíst strategie (DB)')
        load_dn_strategies_button.clicked.connect(self.load_dn_strategies) # Connect to local method
        button_layout.addWidget(load_dn_strategies_button)

        # New button to explicitly load live IB positions for the selected ticker
        load_live_ib_positions_button = QPushButton('Zobrazit živé pozice IB')
        load_live_ib_positions_button.clicked.connect(self.on_show_live_ib_positions_button_click)
        button_layout.addWidget(load_live_ib_positions_button)

        # Add all components to the left layout
        left_layout.addWidget(self.positions_label)
        left_layout.addWidget(self.positions_table)
        left_layout.addWidget(self.details_label)
        left_layout.addWidget(self.details_text)
        
        left_layout.addWidget(self.delta_breakeven_label)
        left_layout.addWidget(self.current_pnl_label)
        
        left_layout.addWidget(self.ib_live_positions_label)
        left_layout.addWidget(self.ib_live_positions_table)

        left_layout.addWidget(self.summary_label)
        left_layout.addWidget(self.summary_table)
        left_layout.addWidget(self.trade_history_label)
        left_layout.addWidget(self.trade_history_table)
        left_layout.addLayout(button_layout)

        # Right side layout for OpenAI Chat
        right_layout = QVBoxLayout()

        # Chat interface
        self.chat_input = QLineEdit(self)
        self.chat_input.setPlaceholderText("Zeptejte se...")

        self.chat_button = QPushButton('Zeptat se GPT')
        self.chat_button.clicked.connect(self.on_ask_gpt)

        # Add model selection
        self.model_label = QLabel("Vybrat model:")
        self.model_selector = QComboBox(self)
        self.model_selector.addItem("gpt-4o")
        self.model_selector.addItem("gpt-3.5-turbo")
        self.model_selector.addItem("gpt-4.1-mini") # This model name might not be standard, verify OpenAI API docs
        self.model_selector.setCurrentText("gpt-4o")

        # Add components to the right layout
        right_layout.addWidget(self.model_label)
        right_layout.addWidget(self.model_selector)
        right_layout.addWidget(self.chat_input)
        right_layout.addWidget(self.chat_button)
        right_layout.addWidget(self.chat_output)

        # Add both side layouts to the main layout
        main_layout.addLayout(left_layout, 70)
        main_layout.addLayout(right_layout, 30)

        self.setLayout(main_layout)

    def load_dn_strategies(self):
        """Delegates to DatabaseManager to load strategy positions."""
        self.db_manager.load_dn_positions(self.positions_table)

    def on_show_live_ib_positions_button_click(self):
        """Handles click on 'Zobrazit živé pozice IB' button, delegates to IBManager."""
        selected_rows = self.positions_table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.information(
                self, "Výběr pozice",
                "Prosím, vyberte strategii z tabulky 'Otevřené Pozice (Strategie)', abyste viděli její živé pozice z IB."
            )
            return
        
        row = selected_rows[0].row()
        ticker = self.positions_table.item(row, 0).text()
        self.ib_manager.load_live_positions(
            ticker,
            self.ib_live_positions_table,
            self.ib_live_positions_label
        )

    def on_position_click(self, row, column):
        """
        Handle the selection of a strategy position, display its details,
        and trigger loading of related IB live positions and historical trades.
        """
        ticker = self.positions_table.item(row, 0).text()
        date_open = self.positions_table.item(row, 1).text()
        
        date_close_item = self.positions_table.item(row, 2)
        date_close = date_close_item.text() if date_close_item and date_close_item.text() else ''

        position = {'ticker': ticker, 'date_open': date_open, 'date_close': date_close}
        
        # Display basic details
        details_text = f"Ticker: {ticker}\n"
        details_text += f"Datum otevření strategie: {date_open}\n"
        if date_close:
            details_text += f"Datum uzavření strategie: {date_close}\n"
        self.details_text.setText(details_text)

        # Load live IB positions for the selected ticker
        self.ib_manager.load_live_positions(
            ticker,
            self.ib_live_positions_table,
            self.ib_live_positions_label
        )

        # Calculate and display current unrealized PnL from IB
        self.ib_manager.calculate_current_unrealized_pnl(ticker, self.current_pnl_label)

        # Load historical trades and PnL summary from DB for the selected strategy
        self.db_manager.load_trade_history_and_summary(
            position,
            self.summary_table,
            self.trade_history_table
        )
        
        # The breakeven calculation is complex and needs more specific strategy data
        # not directly available in this generic `position` dict.
        # It's better to leave it as N/A or implement it more fully within the db_manager
        # if the DB stores all necessary legs for a specific strategy type.
        self.delta_breakeven_label.setText(f'Break-even (Při otevření pro {ticker}): N/A (Vyžaduje detailní data o legách strategie)')


    def on_ask_gpt(self):
        """Delegates to OpenAIChatManager to ask GPT."""
        prompt = self.chat_input.text()
        model = self.model_selector.currentText()
        self.openai_manager.ask_gpt(prompt, model)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = DeltaNeutralApp()
    ex.show()
    sys.exit(app.exec())

