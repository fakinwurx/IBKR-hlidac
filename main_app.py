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
from my_financial_data_manager import FinancialDataManager 
import config

class DeltaNeutralApp(QWidget):
    def __init__(self):
        super().__init__()

        self.chat_output = QTextEdit(self)
        self.chat_output.setPlaceholderText("Systémové zprávy a logy se objeví zde.")
        self.chat_output.setReadOnly(True)

        self.gpt_response_output = QTextEdit(self)
        self.gpt_response_output.setPlaceholderText("Odpověď GPT se objeví zde.")
        self.gpt_response_output.setReadOnly(True)


        self.ib_manager = IBManager(self.chat_output)
        self.db_manager = DatabaseManager(config.DATABASE_PATH, self.chat_output)
        self.openai_manager = OpenAIChatManager(config.OPENAI_API_KEY, self.chat_output, self.gpt_response_output)
        self.financial_data_manager = FinancialDataManager(self.chat_output)

        # NOVÉ: Proměnná pro uchování vybraných dat pozice pro GPT
        self.selected_position_for_gpt = None 

        self.initUI()

    def initUI(self):
        self.setWindowTitle('Delta Neutral Strategie a OpenAI Chat')
        self.setGeometry(100, 100, 1400, 800)

        main_layout = QHBoxLayout()

        left_layout = QVBoxLayout()

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
        # Připojujeme on_position_click k cellClicked pro aktualizaci selected_position_for_gpt
        self.positions_table.cellClicked.connect(self.on_position_click)
        self.positions_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)


        self.details_label = QLabel('Detaily vybrané pozice:')
        self.details_text = QLabel('Vyberte pozici pro zobrazení detailů.')
        
        self.financial_data_group_box = QVBoxLayout()
        self.financial_data_group_label = QLabel("<b>Finanční události:</b>")
        self.financial_data_group_box.addWidget(self.financial_data_group_label)

        self.next_earnings_label = QLabel("Další Earnings: N/A")
        self.financial_data_group_box.addWidget(self.next_earnings_label)
        
        self.next_dividend_date_label = QLabel("Další Dividenda (Ex-Date): N/A")
        self.financial_data_group_box.addWidget(self.next_dividend_date_label)
        
        self.dividend_amount_label = QLabel("Částka Dividendy: N/A")
        self.financial_data_group_box.addWidget(self.dividend_amount_label)
        
        self.dividend_yield_label = QLabel("Dividendový Výnos: N/A")
        self.financial_data_group_box.addWidget(self.dividend_yield_label)
        
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
        
        self.delta_breakeven_label = QLabel('Break-even (Při otevření strategie): N/A')
        self.current_pnl_label = QLabel('Aktuální PnL (Otevřené pozice z IB): N/A')

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

        self.trade_history_label = QLabel('Historie obchodů pro vybraný Ticker:')
        self.trade_history_table = QTableWidget()
        self.trade_history_table.setColumnCount(7) 
        self.trade_history_table.setHorizontalHeaderLabels([
            "Datum", "Symbol", "C/P", "Strike", "Množství", "Realizovaný PnL", "Avg Price"
        ])
        history_header = self.trade_history_table.horizontalHeader()
        history_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        history_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        history_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        history_header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        history_header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        history_header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        history_header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)


        button_layout = QHBoxLayout()

        load_dn_strategies_button = QPushButton('Načíst strategie (DB)')
        load_dn_strategies_button.clicked.connect(self.load_dn_strategies)
        button_layout.addWidget(load_dn_strategies_button)

        load_live_ib_positions_button = QPushButton('Zobrazit živé pozice IB')
        load_live_ib_positions_button.clicked.connect(self.on_show_live_ib_positions_button_click)
        button_layout.addWidget(load_live_ib_positions_button)

        self.show_news_button = QPushButton("Zobrazit novinky pro vybraný ticker")
        self.show_news_button.clicked.connect(self.show_news_for_selected_ticker)
        self.show_news_button.setEnabled(False) 
        button_layout.addWidget(self.show_news_button)


        left_layout.addWidget(self.positions_label)
        left_layout.addWidget(self.positions_table)
        left_layout.addWidget(self.details_label)
        left_layout.addWidget(self.details_text)
        
        left_layout.addLayout(self.financial_data_group_box)
        
        left_layout.addWidget(self.delta_breakeven_label)
        left_layout.addWidget(self.current_pnl_label)
        
        left_layout.addWidget(self.ib_live_positions_label)
        left_layout.addWidget(self.ib_live_positions_table)

        left_layout.addWidget(self.summary_label)
        left_layout.addWidget(self.summary_table)
        left_layout.addWidget(self.trade_history_label)
        left_layout.addWidget(self.trade_history_table)
        left_layout.addLayout(button_layout)

        right_layout = QVBoxLayout()

        right_layout.addWidget(QLabel("<b>Aplikace Log:</b>"))
        right_layout.addWidget(self.chat_output)
        
        right_layout.addWidget(QLabel("<b>OpenAI Chat:</b>"))
        self.chat_input = QLineEdit(self)
        self.chat_input.setPlaceholderText("Zeptejte se GPT...")

        self.chat_button = QPushButton('Zeptat se GPT')
        self.chat_button.clicked.connect(self.on_ask_gpt)

        self.model_label = QLabel("Vybrat model:")
        self.model_selector = QComboBox(self)
        self.model_selector.addItem("gpt-4o")
        self.model_selector.addItem("gpt-3.5-turbo")
        self.model_selector.addItem("gpt-4-turbo") 
        self.model_selector.setCurrentText("gpt-4o")

        right_layout.addWidget(self.model_label)
        right_layout.addWidget(self.model_selector)
        right_layout.addWidget(self.chat_input)
        right_layout.addWidget(self.chat_button)
        right_layout.addWidget(self.gpt_response_output)


        main_layout.addLayout(left_layout, 65) 
        main_layout.addLayout(right_layout, 35) 

        self.setLayout(main_layout)

    def load_dn_strategies(self):
        """Delegates to DatabaseManager to load strategy positions."""
        self.db_manager.load_dn_positions(self.positions_table)
        # Reset selected position data when strategies are reloaded
        self.selected_position_for_gpt = None 


    def on_show_live_ib_positions_button_click(self):
        """Handles click on 'Zobrazit živé pozice IB' button, delegates to IBManager."""
        # Použijeme self.selected_position_for_gpt pro získání tickeru, pokud je pozice vybrána
        if self.selected_position_for_gpt and 'ticker' in self.selected_position_for_gpt:
            ticker = self.selected_position_for_gpt['ticker']
            self.ib_manager.load_live_positions(
                ticker,
                self.ib_live_positions_table,
                self.ib_live_positions_label
            )
        else:
            QMessageBox.information(
                self, "Výběr pozice",
                "Prosím, vyberte strategii z tabulky 'Otevřené Pozice (Strategie)', abyste viděli její živé pozice z IB."
            )
            return

    def on_position_click(self, row, column):
        """
        Handle the selection of a strategy position, display its details,
        and trigger loading of related IB live positions and historical trades.
        Also updates self.selected_position_for_gpt.
        """
        ticker = self.positions_table.item(row, 0).text()
        date_open = self.positions_table.item(row, 1).text()
        
        date_close_item = self.positions_table.item(row, 2)
        date_close = date_close_item.text() if date_close_item and date_close_item.text() else ''

        # Uložíme vybranou pozici do instanční proměnné
        self.selected_position_for_gpt = {
            'ticker': ticker,
            'date_open': date_open,
            'date_close': date_close
        }
        print(f"DEBUG: Pozice kliknuta a uložena: {self.selected_position_for_gpt}")

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
        position_data_for_db = {
            'ticker': ticker,
            'date_open': date_open,
            'date_close': date_close # Posíláme i date_close
        }
        self.db_manager.load_trade_history_and_summary(
            position_data_for_db,
            self.summary_table,
            self.trade_history_table
        )
        
        # Load and display financial events
        earnings_date = self.financial_data_manager.get_next_earnings_date(ticker)
        self.next_earnings_label.setText(f"Další Earnings: {earnings_date}")

        dividend_info = self.financial_data_manager.get_next_dividend_info(ticker)
        amount_display = f"{dividend_info['amount']:.2f}" if isinstance(dividend_info['amount'], (int, float)) else str(dividend_info['amount'])
        self.next_dividend_date_label.setText(f"Další Dividenda (Ex-Date): {dividend_info['date']}")
        self.dividend_amount_label.setText(f"Částka Dividendy: {amount_display}")
        self.dividend_yield_label.setText(f"Dividendový Výnos: {dividend_info['yield_percent']}")

        self.delta_breakeven_label.setText(f'Break-even (Při otevření pro {ticker}): N/A (Vyžaduje detailní data o legách strategie)')

        self.show_news_button.setEnabled(True)


    def on_ask_gpt(self):
        """
        Delegates to OpenAIChatManager to ask GPT, including relevant position data.
        """
        user_prompt = self.chat_input.text().strip()
        model = self.model_selector.currentText()

        if not user_prompt:
            self.chat_output.append("<span style='color:red;'>Prosím, zadejte text dotazu pro GPT.</span>")
            return

        # Prepare context data from the selected position
        context_data = ""
        # Použijeme self.selected_position_for_gpt pro získání dat
        if self.selected_position_for_gpt:
            ticker = self.selected_position_for_gpt['ticker']
            date_open = self.selected_position_for_gpt['date_open']
            
            context_data += f"\n\nAnalyzujte následující data o pozici a strategii:\n"
            context_data += f"- Ticker: {ticker}\n"
            context_data += f"- Datum otevření strategie: {date_open}\n"
            context_data += f"- Další Earnings: {self.next_earnings_label.text().replace('Další Earnings: ', '')}\n"
            context_data += f"- Další Dividenda (Ex-Date): {self.next_dividend_date_label.text().replace('Další Dividenda (Ex-Date): ', '')}\n"
            context_data += f"- Částka Dividendy: {self.dividend_amount_label.text().replace('Částka Dividendy: ', '')}\n"
            context_data += f"- Dividendový Výnos: {self.dividend_yield_label.text().replace('Dividendový Výnos: ', '')}\n"
            context_data += f"- Aktuální Nerealizovaný PnL: {self.current_pnl_label.text().replace('Aktuální PnL (Otevřené pozice z IB): ', '')}\n"
            
            live_positions_data = []
            for r in range(self.ib_live_positions_table.rowCount()):
                # Upravená kontrola pro zohlednění prázdných "Právo" a "Strike" pro akcie
                symbol_item = self.ib_live_positions_table.item(r, 0)
                sec_type_item = self.ib_live_positions_table.item(r, 1)
                right_item = self.ib_live_positions_table.item(r, 2)
                strike_item = self.ib_live_positions_table.item(r, 3)
                qty_item = self.ib_live_positions_table.item(r, 4)
                market_val_item = self.ib_live_positions_table.item(r, 5)
                avg_cost_item = self.ib_live_positions_table.item(r, 6)
                unrealized_pnl_item = self.ib_live_positions_table.item(r, 7)

                # Zajištění, že existují základní položky a jejich text
                if (symbol_item and symbol_item.text() and 
                    sec_type_item and sec_type_item.text() and
                    qty_item and qty_item.text() and
                    market_val_item and market_val_item.text() and
                    avg_cost_item and avg_cost_item.text() and
                    unrealized_pnl_item and unrealized_pnl_item.text()):
                    
                    symbol = symbol_item.text()
                    sec_type = sec_type_item.text()
                    right = right_item.text() if right_item else "" # Prázdný string, pokud položka neexistuje
                    strike = strike_item.text() if strike_item else "" # Prázdný string, pokud položka neexistuje
                    qty = qty_item.text()
                    market_val = market_val_item.text()
                    avg_cost = avg_cost_item.text()
                    unrealized_pnl = unrealized_pnl_item.text()
                    
                    live_positions_data.append(
                        f"  - {symbol} ({sec_type}, Právo='{right}', Strike='{strike}'): Množství={qty}, "
                        f"Tržní hodnota={market_val}, Prům. cena={avg_cost}, Nerealizovaný PnL={unrealized_pnl}"
                    )
                else:
                    self.chat_output.append(f"<span style='color:orange;'>Upozornění: Některá data živých pozic jsou neúplná v řádku {r}.</span>")
                    print(f"DEBUG: Skipping incomplete live position row {r}.")


            if live_positions_data:
                context_data += "Živé pozice z IB pro vybraný ticker:\n" + "\n".join(live_positions_data)
            else:
                context_data += "Živé pozice z IB pro vybraný ticker: Žádné dostupné nebo neúplné data.\n"

            if self.summary_table.rowCount() > 0:
                summary_items = [self.summary_table.item(0, col) for col in range(4)]
                if all(item and item.text() for item in summary_items):
                    summary_ticker = summary_items[0].text()
                    realized_pnl = summary_items[1].text()
                    net_cash = summary_items[2].text()
                    fx_pnl = summary_items[3].text()
                    context_data += f"\nSouhrn realizovaného PnL pro {summary_ticker}: " \
                                    f"Realizovaný PnL={realized_pnl}, Čistá hotovost={net_cash}, FX PnL={fx_pnl}\n"
                else:
                    self.chat_output.append("<span style='color:orange;'>Upozornění: Souhrn PnL je neúplný.</span>")
                    print("DEBUG: Skipping incomplete summary PnL data.")
            else:
                context_data += "Souhrn realizovaného PnL: Žádné dostupné data.\n"

        else:
            context_data = "\n(Žádná pozice není vybrána, poskytuji obecnou odpověď bez kontextu pozice.)"
            self.chat_output.append("<span style='color:orange;'>Upozornění: Pro poskytnutí kontextu pro GPT prosím nejprve klikněte na řádek pozice v tabulce 'Otevřené Pozice (Strategie)'.</span>")


        full_prompt = f"{user_prompt}\n{context_data}"

        print("\n--- Odesílám do GPT (celý prompt): ---")
        print(full_prompt)
        print("---------------------------------------\n")

        self.openai_manager.ask_gpt(full_prompt, model)
        self.chat_input.clear()


    def show_news_for_selected_ticker(self):
        """Otevře okno s novinkami pro vybraný ticker."""
        # Použijeme self.selected_position_for_gpt pro získání tickeru, pokud je pozice vybrána
        if self.selected_position_for_gpt and 'ticker' in self.selected_position_for_gpt:
            ticker = self.selected_position_for_gpt['ticker']
            self.chat_output.append(f"Otevírám okno s novinkami pro ticker: {ticker}")
            self.news_window = NewsWindow(ticker, self.chat_output, self) 
            self.news_window.show()
        else:
            self.chat_output.append("<span style='color:orange;'>Prosím, vyberte ticker z tabulky DN, abyste zobrazili novinky.</span>")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = DeltaNeutralApp()
    ex.show()
    sys.exit(app.exec())
