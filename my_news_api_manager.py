# my_news_api_manager.py
import requests
from datetime import datetime, timedelta
import config # Pro získání API klíče
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer # Importujeme VADER Sentiment Analyzer

class NewsAPIManager:
    def __init__(self, chat_output_widget):
        """
        Inicializuje NewsAPIManager.

        Args:
            chat_output_widget (QTextEdit): Widget pro výstup zpráv.
        """
        self.chat_output = chat_output_widget
        self.api_key = config.NEWS_API_KEY # Získání API klíče z config.py
        
        # Inicializace VADER sentiment analyzátoru
        self.sid_obj = SentimentIntensityAnalyzer()

        if not self.api_key:
            self.chat_output.append("<span style='color:orange;'>Upozornění: API klíč pro News API není nastaven v config.py. Novinky nemusí fungovat.</span>")
            print("WARNING: News API key is not set in config.py.")

    def get_upcoming_news(self, ticker, days_ahead=30):
        """
        Získá nedávné novinky pro daný ticker, které mohou ovlivnit akcii.
        Používá Marketaux News API a provádí sentiment analýzu pomocí VADER.

        Args:
            ticker (str): Symbol akcie (např. "M").
            days_ahead (int): Počet dnů zpět, pro které se mají zprávy hledat.
                              (Marketaux API poskytuje historické/nedávné zprávy, ne budoucí události)

        Returns:
            list: Seznam slovníků s detaily novinek (např. [{'date': 'YYYY-MM-DD', 'title': 'Nadpis', 'source': 'Zdroj', 'url': 'URL', 'sentiment': float}]).
                  Vrátí prázdný seznam v případě chyby nebo absence novinek.
        """
        if not self.api_key:
            self.chat_output.append("<span style='color:red;'>CHYBA: API klíč pro Marketaux není nastaven. Nelze načíst novinky.</span>")
            print("ERROR: Marketaux API key is not set. Cannot fetch news.")
            return []

        self.chat_output.append(f"Pokouším se získat novinky pro {ticker} z posledních {days_ahead} dnů z Marketaux API...")
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_ahead)
        start_date_str = start_date.strftime('%Y-%m-%d')
        
        # Mapování tickerů na plné názvy společností pro zpřesnění vyhledávání
        company_names = {
            "M": "Macy's",
            "SOFI": "SoFi Technologies",
            "KHC": "Kraft Heinz"
        }
        
        keywords = ticker
        if ticker in company_names:
            keywords = f"{ticker} {company_names[ticker]}"

        URL = f"https://api.marketaux.com/v1/news/all?symbols={ticker}&published_after={start_date_str}&language=en&api_token={self.api_key}&limit=100&keywords={keywords}"
        
        try:
            response = requests.get(URL)
            response.raise_for_status() 
            data = response.json()
            
            news_items = []
            for article in data.get('data', []):
                title_lower = article.get('title', '').lower()
                source_lower = article.get('source', '').lower()

                # Příklad velmi jednoduché filtrace:
                if ticker == "M" and ("amazon" in title_lower or "amazon" in source_lower):
                     print(f"DEBUG: Ignoring potentially irrelevant news for {ticker}: {title_lower}")
                     continue 
                
                # Provedení sentiment analýzy
                text_to_analyze = article.get('snippet') or article.get('description') or article.get('title', '')
                sentiment_score = 0.0 # Defaultní hodnota
                if text_to_analyze:
                    vs = self.sid_obj.polarity_scores(text_to_analyze)
                    sentiment_score = vs['compound'] # Compound score je normalizované složené skóre (-1.0 až +1.0)

                news_items.append({
                    'date': article.get('published_at', '')[:10],
                    'title': article.get('title', 'Bez nadpisu'),
                    'source': article.get('source', 'Neznámý zdroj'),
                    'url': article.get('url', '#'),
                    'sentiment': sentiment_score # Přidáme skóre sentimentu
                })
            
            if news_items:
                self.chat_output.append(f"<span style='color:green;'>Načteno a analyzováno {len(news_items)} novinek pro {ticker} z Marketaux.</span>")
            else:
                self.chat_output.append(f"<span style='color:orange;'>Pro {ticker} nebyly z Marketaux nalezeny žádné novinky v daném období.</span>")
            return news_items

        except requests.exceptions.RequestException as e:
            self.chat_output.append(f"<span style='color:red;'>CHYBA při získávání novinek z Marketaux API pro {ticker}: {e}</span>")
            print(f"ERROR: Marketaux API request failed for {ticker}: {e}")
            return []
        except Exception as e:
            self.chat_output.append(f"<span style='color:red;'>Neočekávaná chyba při zpracování novinek z Marketaux pro {ticker}: {e}</span>")
            print(f"ERROR: Unexpected error processing Marketaux news for {ticker}: {e}")
            return []
