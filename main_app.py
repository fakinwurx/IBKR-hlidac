# main_app.py
import sys
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QLineEdit, QTextEdit, QComboBox, QHeaderView,
    QMessageBox, QDialog, QFormLayout, QDialogButtonBox, QDateEdit
)
from PyQt6.QtCore import QDate
from PyQt6.QtGui import QColor

# Import the new manager classes and config
from ib_manager import IBManager
from database_manager import DatabaseManager
from openai_chat_manager import OpenAIChatManager
from my_financial_data_manager import FinancialDataManager
import config

# Import modules needed for the new script (kód číslo 2)
# Ujistěte se, že jsou nainstalovány!
# pip install ib_insync
# pip install pandas
# pip install sqlite3 (obvykle je součástí Pythonu)
import ib_insync
import pandas as pd
import sqlite3 as sq
from datetime import datetime
import os

class AddStrategyDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Přidat novou Delta Neutral strategii")
        self.layout = QFormLayout(self)
        
        self.ticker_input = QLineEdit(self)
        self.date_input = QDateEdit(self)
        self.date_input.setDate(QDate.currentDate())
        self.date_input.setCalendarPopup(True)
        self.date_input.setDisplayFormat("yyyy-MM-dd")
        
        self.layout.addRow("Ticker:", self.ticker_input)
        self.layout.addRow("Datum vstupu:", self.date_input)
        
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.layout.addWidget(self.buttons)
        
        self.ticker = None
        self.date_open = None

    def accept(self):
        self.ticker = self.ticker_input.text().strip().upper()
        self.date_open = self.date_input.date().toString("yyyy-MM-dd")
        if not self.ticker or not self.date_open:
            QMessageBox.warning(self, "Chyba", "Prosím vyplňte obě pole.")
            return
        super().accept()

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
        # Povolíme editaci buněk v tabulce pro datumy
        self.positions_table.setEditTriggers(QTableWidget.EditTrigger.AnyKeyPressed | QTableWidget.EditTrigger.DoubleClicked)
        # Připojujeme on_position_click k cellClicked pro aktualizaci selected_position_for_gpt
        self.positions_table.cellClicked.connect(self.on_position_click)
        # Nový signál pro sledování změn v buňkách
        self.positions_table.cellChanged.connect(self.on_position_cell_edited)
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
        
        # NOVINKA: Změna počtu sloupců na 8, aby se vešel skrytý tradeId
        self.trade_history_table = QTableWidget()
        self.trade_history_table.setColumnCount(8) 
        self.trade_history_table.setHorizontalHeaderLabels([
            "Datum", "Symbol", "C/P", "Strike", "Množství", "Realizovaný PnL", "Avg Price", "Trade ID"
        ])
        # NOVINKA: Skrytí sloupce "Trade ID"
        self.trade_history_table.hideColumn(7)
        history_header = self.trade_history_table.horizontalHeader()
        history_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        history_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        history_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        history_header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        history_header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        history_header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        history_header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        
        # Připojíme on_trade_history_click k cellClicked
        self.trade_history_table.cellClicked.connect(self.on_trade_history_click)

        button_layout = QHBoxLayout()

        add_dn_entry_button = QPushButton('Přidat záznam DN')
        add_dn_entry_button.clicked.connect(self.add_dn_entry)
        button_layout.addWidget(add_dn_entry_button)

        load_dn_strategies_button = QPushButton('Načíst strategie (DB)')
        load_dn_strategies_button.clicked.connect(self.load_dn_strategies)
        button_layout.addWidget(load_dn_strategies_button)
        
        # TLAČÍTKO PRO SMAZÁNÍ STRATEGIE
        delete_dn_entry_button = QPushButton('Smazat vybraný záznam DN')
        delete_dn_entry_button.clicked.connect(self.delete_selected_dn_entry)
        button_layout.addWidget(delete_dn_entry_button)

        load_live_ib_positions_button = QPushButton('Zobrazit živé pozice IB')
        load_live_ib_positions_button.clicked.connect(self.on_show_live_ib_positions_button_click)
        button_layout.addWidget(load_live_ib_positions_button)
        
        # TLAČÍTKO PRO SPUŠTĚNÍ FLEXREPORTU
        run_flexreport_button = QPushButton('Spustit FlexReport (Kód 2)')
        run_flexreport_button.clicked.connect(self.on_run_flexreport)
        button_layout.addWidget(run_flexreport_button)

        self.show_news_button = QPushButton("Zobrazit novinky pro vybraný ticker")
        self.show_news_button.clicked.connect(self.show_news_for_selected_ticker)
        self.show_news_button.setEnabled(False) 
        button_layout.addWidget(self.show_news_button)
        
        # TLAČÍTKO PRO SMAZÁNÍ ZÁZNAMU Z HISTORIE OBCHODŮ
        delete_trade_history_button = QPushButton('Smazat vybraný záznam z historie')
        delete_trade_history_button.clicked.connect(self.delete_selected_trade_history_entry)
        button_layout.addWidget(delete_trade_history_button)

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

    def on_position_cell_edited(self, row, column):
        """
        Handles cell edits in the positions table.
        Updates the database with the new data.
        """
        # Ignorovat sloupce, které by neměly být editovatelné (např. Ticker)
        if column != 1 and column != 2:
            return

        # Získáme všechny hodnoty z řádku, abychom měli unikátní identifikátor
        ticker = self.positions_table.item(row, 0).text()
        new_value = self.positions_table.item(row, column).text()
        
        # Získáme starou hodnotu 'date_open' pro identifikaci
        # Uložíme si ji do proměnné před jakoukoliv změnou
        original_date_open_item = self.positions_table.item(row, 1)
        original_date_close_item = self.positions_table.item(row, 2)
        
        # Získáme hodnoty pro primární klíč
        original_date_open = original_date_open_item.text() if original_date_open_item else None
        original_date_close = original_date_close_item.text() if original_date_close_item else ''

        # Určíme, který sloupec se změnil
        column_name = 'date_open' if column == 1 else 'date_close'

        if ticker and original_date_open:
            self.db_manager.update_dn_strategy(ticker, original_date_open, original_date_close, column_name, new_value)
        else:
            self.chat_output.append("<span style='color:red;'>Chyba: Nepodařilo se najít data pro aktualizaci.</span>")

    def add_dn_entry(self):
        """Otevře dialog pro přidání nového záznamu Delta Neutral strategie."""
        dialog = AddStrategyDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            ticker = dialog.ticker
            date_open = dialog.date_open
            
            try:
                self.db_manager.add_dn_entry(ticker, date_open)
                self.chat_output.append(f"<span style='color:green;'>Úspěšně přidán záznam pro {ticker} s datem {date_open}.</span>")
                self.load_dn_strategies()
            except Exception as e:
                self.chat_output.append(f"<span style='color:red;'>Chyba při přidávání záznamu: {e}</span>")

    def load_dn_strategies(self):
        """Delegates to DatabaseManager to load strategy positions."""
        # Odpojení signálu, abychom zabránili nechtěnému spuštění při načítání dat
        try:
            self.positions_table.cellChanged.disconnect(self.on_position_cell_edited)
        except TypeError:
            pass # Signál není připojen, neřešit
        
        # Využijeme metodu, která načte VŠECHNY DN záznamy, včetně uzavřených
        entries = self.db_manager.get_all_dn_entries()
        self.positions_table.setRowCount(len(entries))
        for i, entry in enumerate(entries):
            date_open, ticker, date_close = entry
            self.positions_table.setItem(i, 0, QTableWidgetItem(ticker))
            self.positions_table.setItem(i, 1, QTableWidgetItem(date_open))
            self.positions_table.setItem(i, 2, QTableWidgetItem(date_close))

        # Znovu připojení signálu po načtení dat
        self.positions_table.cellChanged.connect(self.on_position_cell_edited)
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

    def on_trade_history_click(self, row, column):
        """Zpracuje kliknutí na řádek v tabulce historie obchodů."""
        # Tato metoda zatím nic nedělá, ale může být použita v budoucnu
        # pro zobrazení detailů obchodu nebo jiné akce.
        pass
    
    def delete_selected_dn_entry(self):
        """
        Smaže vybraný záznam z tabulky DN a z databáze po potvrzení.
        """
        row_index = self.positions_table.currentRow()
        if row_index == -1:
            self.chat_output.append("<span style='color:orange;'>Prosím, vyberte záznam, který chcete smazat.</span>")
            return

        date_open_item = self.positions_table.item(row_index, 1)
        ticker_item = self.positions_table.item(row_index, 0)

        if date_open_item and ticker_item:
            date_open = date_open_item.text()
            ticker = ticker_item.text()
            
            # Zobrazit dialog pro potvrzení smazání
            confirm_dialog = QMessageBox()
            confirm_dialog.setIcon(QMessageBox.Icon.Question)
            confirm_dialog.setWindowTitle("Potvrzení smazání")
            confirm_dialog.setText(f"Opravdu chcete smazat záznam pro '{ticker}' s datem '{date_open}'?\nTato akce je nevratná.")
            confirm_dialog.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            confirm_dialog.setDefaultButton(QMessageBox.StandardButton.No)
            
            if confirm_dialog.exec() == QMessageBox.StandardButton.Yes:
                try:
                    self.db_manager.delete_dn_entry(ticker, date_open)
                    self.load_dn_strategies()
                except Exception as e:
                    self.chat_output.append(f"<span style='color:red;'>Nepodařilo se smazat záznam: {e}</span>")
        else:
            self.chat_output.append("<span style='color:red;'>Chyba: Vybraný řádek neobsahuje platná data.</span>")
            
    def delete_selected_trade_history_entry(self):
        """
        Smaže vybraný záznam z tabulky historie obchodů a z databáze po potvrzení.
        """
        row_index = self.trade_history_table.currentRow()
        if row_index == -1:
            self.chat_output.append("<span style='color:orange;'>Prosím, vyberte záznam z historie obchodů, který chcete smazat.</span>")
            return
            
        # NOVINKA: Získání Trade ID ze skrytého sloupce (index 7)
        trade_id_item = self.trade_history_table.item(row_index, 7) 
        
        # Zkontrolujeme, zda máme data pro smazání
        if trade_id_item and trade_id_item.text():
            trade_id = trade_id_item.text()
            symbol = self.trade_history_table.item(row_index, 1).text()
            
            # Zobrazit dialog pro potvrzení smazání
            confirm_dialog = QMessageBox()
            confirm_dialog.setIcon(QMessageBox.Icon.Question)
            confirm_dialog.setWindowTitle("Potvrzení smazání")
            confirm_dialog.setText(f"Opravdu chcete smazat záznam pro '{symbol}' s ID obchodu '{trade_id}'?\nTato akce je nevratná.")
            confirm_dialog.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            confirm_dialog.setDefaultButton(QMessageBox.StandardButton.No)
            
            if confirm_dialog.exec() == QMessageBox.StandardButton.Yes:
                try:
                    conn = sq.connect(config.DATABASE_PATH)
                    cursor = conn.cursor()
                    
                    # Použijeme Trade ID pro přesné smazání
                    cursor.execute("""
                        DELETE FROM IBFlexQueryCZK
                        WHERE tradeId = ?
                    """, (trade_id,))
                    
                    conn.commit()
                    conn.close()
                    
                    self.chat_output.append(f"<span style='color:green;'>Záznam pro '{symbol}' s ID '{trade_id}' byl úspěšně smazán z historie obchodů.</span>")
                    
                    # Znovu načteme historii obchodů, abychom aktualizovali tabulku
                    if self.selected_position_for_gpt:
                        position_data_for_db = {
                            'ticker': self.selected_position_for_gpt['ticker'],
                            'date_open': self.selected_position_for_gpt['date_open'],
                            'date_close': self.selected_position_for_gpt['date_close']
                        }
                        self.db_manager.load_trade_history_and_summary(
                            position_data_for_db,
                            self.summary_table,
                            self.trade_history_table
                        )
                except Exception as e:
                    self.chat_output.append(f"<span style='color:red;'>Nepodařilo se smazat záznam z historie: {e}</span>")
        else:
            self.chat_output.append("<span style='color:red;'>Chyba: Vybraný řádek historie neobsahuje platná data pro smazání.</span>")

    def on_run_flexreport(self):
        """
        NOVÁ METODA pro spuštění FlexReport skriptu.
        Opravená verze s kódem uvnitř metody.
        """
        conn = None # Zajišťujeme, že proměnná conn je inicializována
        self.chat_output.append("<span style='color:blue;'>Spouštím stahování a ukládání FlexReportu...</span>")
        
        try:
            # Získání hodnot z konfiguračního souboru a odstranění bílých znaků
            token = config.TOKEN.strip()
            queryid = config.QUERY_ID.strip()
            database_path = config.DATABASE_PATH # Správná proměnná z config.py

            # Připojení k databázi SQLite
            conn = sq.connect(database_path)
            cur = conn.cursor()
            
            self.chat_output.append("Všechna data z tabulky 'IBFlexQueryCZK' byla smazána.")
            cur.execute('''DELETE FROM IBFlexQueryCZK''')
            conn.commit()

            # Stažení nových dat z FlexReportu
            fr = ib_insync.FlexReport(token, queryid)
            pdtrades = fr.df('Trade')
            
            self.chat_output.append(f"Úspěšně staženo {len(pdtrades)} záznamů z FlexReportu.")
            
            # Vložení nových dat do databáze (smazání předchozích a vložení nových)
            pdtrades.to_sql('IBFlexQueryCZK', conn, if_exists='replace', index=False)

            # Získání počtu nově přidaných řádků
            self.chat_output.append(f"Úspěšně vloženo {len(pdtrades)} nových obchodů do databáze 'IBFlexQueryCZK'.")
            
        except Exception as e:
            self.chat_output.append(f"<span style='color:red;'>Chyba při spouštění FlexReport skriptu: {e}</span>")
            print(f"Chyba při spouštění FlexReport skriptu: {e}", file=sys.stderr)
        finally:
            if conn:
                conn.close()
        

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
