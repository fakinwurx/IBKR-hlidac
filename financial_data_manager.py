# my_financial_data_manager.py
import yfinance as yf
from datetime import datetime, timedelta
import pandas as pd # Importujeme pandas pro práci s DataFrame
import config # Pro získání API klíče, pokud by bylo potřeba (momentálně se nepoužívá, ale je dobré ho tam mít)

class FinancialDataManager:
    def __init__(self, chat_output_widget):
        """
        Inicializuje FinancialDataManager pro získávání finančních dat.

        Args:
            chat_output_widget (QTextEdit): Widget pro výstup zpráv.
        """
        self.chat_output = chat_output_widget

    def get_next_earnings_date(self, ticker):
        """
        Získá datum příštích earnings pro daný ticker pomocí yfinance.
        Zkusí různé atributy pro robustnost.

        Args:
            ticker (str): Symbol akcie.

        Returns:
            str: Datum příštích earnings ve formátu RRRR-MM-DD, nebo 'N/A' pokud není nalezeno.
        """
        try:
            stock = yf.Ticker(ticker)
            
            # Zkusíme nejprve earnings_dates DataFrame (nejpřesnější pro budoucí data)
            try:
                earnings_dates_df = stock.earnings_dates
                if not earnings_dates_df.empty:
                    today = datetime.now().date()
                    # Zajištění, že index je datetime, a filtrace
                    # Pokud index obsahuje timezone, převedeme na naive datetime (bez timezone)
                    if earnings_dates_df.index.tz is not None:
                        earnings_dates_df.index = earnings_dates_df.index.tz_convert(None)
                    
                    upcoming_earnings = earnings_dates_df[earnings_dates_df.index.date >= today].sort_index(ascending=True)

                    if not upcoming_earnings.empty:
                        next_earnings_date = upcoming_earnings.index[0].strftime('%Y-%m-%d')
                        self.chat_output.append(f"Earnings datum pro {ticker} načteno z earnings_dates: {next_earnings_date}.")
                        return next_earnings_date
            except Exception as e_df:
                self.chat_output.append(f"DEBUG: Chyba při získávání earnings z earnings_dates pro {ticker}: {e_df}")

            # Pokud stock.earnings_dates selhalo nebo nenašlo budoucí, zkusíme 'earningsCalendar' z info
            info = stock.info
            earnings_calendar_info = info.get('earningsCalendar') # Toto může být list dictů nebo dict
            
            if earnings_calendar_info:
                # earningsCalendar může být dict s klíčem 'earningsDate', nebo list dictů
                if isinstance(earnings_calendar_info, dict) and 'earningsDate' in earnings_calendar_info:
                    date_str = earnings_calendar_info['earningsDate']
                    try:
                        date_obj = datetime.strptime(date_str.split('T')[0], '%Y-%m-%d').date()
                        if date_obj >= datetime.now().date():
                            self.chat_output.append(f"Earnings datum pro {ticker} načteno z info['earningsCalendar']: {date_obj.strftime('%Y-%m-%d')}.")
                            return date_obj.strftime('%Y-%m-%d')
                    except ValueError:
                        pass # Ignore malformed date strings
                elif isinstance(earnings_calendar_info, list) and earnings_calendar_info:
                    for entry in earnings_calendar_info:
                        if 'earningsDate' in entry:
                            date_str = entry['earningsDate']
                            try:
                                date_obj = datetime.strptime(date_str.split('T')[0], '%Y-%m-%d').date()
                                if date_obj >= datetime.now().date():
                                    self.chat_output.append(f"Earnings datum pro {ticker} načteno z info['earningsCalendar'] (list): {date_obj.strftime('%Y-%m-%d')}.")
                                    return date_obj.strftime('%Y-%m-%d')
                            except ValueError:
                                pass
            
            # Poslední pokus: 'earningsDate' přímo z info (pro některé starší verze yfinance nebo tickery)
            if 'earningsDate' in info and info['earningsDate']:
                date_str = info['earningsDate']
                try:
                    date_obj = datetime.strptime(date_str.split('T')[0], '%Y-%m-%d').date()
                    if date_obj >= datetime.now().date():
                        self.chat_output.append(f"Earnings datum pro {ticker} načteno z info['earningsDate']: {date_obj.strftime('%Y-%m-%d')}.")
                        return date_obj.strftime('%Y-%m-%d')
                except ValueError:
                    pass

            self.chat_output.append(f"Pro {ticker} nebylo nalezeno žádné nadcházející earnings datum (yfinance - všechny metody).")
            return "N/A"
        except Exception as e:
            self.chat_output.append(f"<span style='color:red;'>Chyba při získávání earnings dat pro {ticker} (yfinance - obecná chyba): {e}</span>")
            print(f"ERROR: Failed to get earnings data for {ticker} (yfinance - general error): {e}")
            return "Chyba"

    def get_next_dividend_info(self, ticker):
        """
        Získá informace o příští dividendě pro daný ticker pomocí yfinance.
        Zkoumá 'dividends' history a 'info' dict pro yield.

        Args:
            ticker (str): Symbol akcie.

        Returns:
            dict: Slovník s 'date' (Ex-Dividend Date), 'amount', 'yield_percent',
                  nebo výchozí hodnoty, pokud nejsou nalezeny.
        """
        try:
            stock = yf.Ticker(ticker)
            
            dividends_series = stock.dividends
            
            next_dividend_date = 'N/A'
            next_dividend_amount = 'N/A'
            
            if not dividends_series.empty:
                # Zajištění, že index je datetime a odstranění timezone
                if dividends_series.index.tz is not None:
                    dividends_series.index = dividends_series.index.tz_convert(None)

                today = datetime.now().date()
                
                # Filtr pro budoucí nebo velmi nedávné dividendy (např. posledních 30 dní, pokud nejsou žádné budoucí)
                relevant_dividends = dividends_series[dividends_series.index.date >= today - timedelta(days=30)].sort_index(ascending=True)

                # Najdeme nejbližší budoucí ex-dividend date
                for ex_date, amount in relevant_dividends.items():
                    if ex_date.date() >= today:
                        next_dividend_date = ex_date.strftime('%Y-%m-%d')
                        next_dividend_amount = float(amount)
                        break
                
                # Pokud se nenašla žádná budoucí dividenda, vezmeme tu nejnovější známou
                if next_dividend_date == 'N/A' and not dividends_series.empty:
                    last_dividend_date = dividends_series.index.max()
                    if last_dividend_date:
                        last_dividend_value = dividends_series.loc[last_dividend_date]
                        next_dividend_date = last_dividend_date.strftime('%Y-%m-%d')
                        next_dividend_amount = float(last_dividend_value)
                        self.chat_output.append(f"Nejsou nadcházející dividendy pro {ticker}. Zobrazuji poslední známou.")
                    else:
                        self.chat_output.append(f"Pro {ticker} nebyly nalezeny žádné dividendové informace z historie (yfinance).")

            # Dividend Yield z info dictionary
            info = stock.info
            # dividendYield je často procentuální (např. 0.02 pro 2%)
            dividend_yield_percent = info.get('dividendYield') 
            if dividend_yield_percent is not None:
                dividend_yield_percent = f"{dividend_yield_percent * 100:.2f}%"
            else:
                # Zkusíme trailingAnnualDividendYield jako alternativu
                trailing_yield = info.get('trailingAnnualDividendYield')
                if trailing_yield is not None:
                    dividend_yield_percent = f"{trailing_yield * 100:.2f}%"
                else:
                    dividend_yield_percent = "N/A"

            if next_dividend_date != 'N/A' and next_dividend_amount != 'N/A':
                self.chat_output.append(f"Dividendové info pro {ticker} načteno.")
                return {
                    'date': next_dividend_date,
                    'amount': next_dividend_amount,
                    'yield_percent': dividend_yield_percent
                }
            else:
                self.chat_output.append(f"Pro {ticker} nebyly nalezeny nadcházející dividendové informace (yfinance).")
                return {'date': 'N/A', 'amount': 'N/A', 'yield_percent': 'N/A'}
        except Exception as e:
            self.chat_output.append(f"<span style='color:red;'>Chyba při získávání dividendových dat pro {ticker} (yfinance): {e}</span>")
            print(f"ERROR: Failed to get dividend data for {ticker} (yfinance): {e}")
            return {'date': 'Chyba', 'amount': 'Chyba', 'yield_percent': 'Chyba'}

