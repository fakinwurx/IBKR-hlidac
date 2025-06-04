# parametry emailu
# SendMail - False / True - urcuje zda system odesila emaily
# SmtpServer, FromAddress, Password - nastavení serveru a autorizace odchozí posty
# ToAdress - cílový email - ['first@example.com', 'second@example.com']
setmail = {
        'SendMail' : True,
        'FromAddress' : 'tomasxxxxx@seznam.cz',
        'Password' : 'xxxxx@-BQ', # nove heslo pro SMTP a postovni klienty: neco_1598@-BQ
        'ToAddress' : 'tomas.xxxxx@gmail.com',
       #'ToAddress' : ['tomas.xxxxx@gmail.com', 'xxxxx@email.cz'],
        'SmtpServer' : 'smtp.seznam.cz',
        'Port' : 587
}
# cesta k databazi
setsql = {
        'sqldata' : 'data\IBFlexQuery.db'
}

# název soubory s logy systemu
setlogfile = {
        'filename' : 'autotrader.log'
}
# token
token = 'your FLEX QUERY TOKEN'
# Query ID

queryid = '622438'
# queryid = '877428' # pro Year To Date data

# kurz pro prepocet kapitalu, pouzije se v pripade chyby nacteni kurzu CZK/USD z IB
static_exrate = 22.62

# nastaveni cesty kam AmiBroker uklada soubory projektu 
# napr. 'c:/Programy/AmiBroker/Projekty/'
# ja mam: c:\Program Files\AmiBroker\Formulas\Custom\AnalysisProjectsAndBatch\
# já mam s obracenýmí lomítky c:/Program Files/AmiBroker/Formulas/Custom/AnalysisProjectsAndBatch/
amibroker = {
        'ProjectPath' : 'c:/Program Files/AmiBroker/Formulas/Custom/AnalysisProjectsAndBatch/'
}

# uprava insporovana uživatelem s nickem Ichram
# uprava nazvu tickeru pro IB
tickers = {"BF-A":"BF A", "BF-B":"BF B", "BRK-B":"BRK B", "CRD-A":"CRD A", "CWEN-A":"CWEN A", "GEF-B":"GEF B", "HEI-A": "HEI A", "JW-A":"JW A", "LEN-B":"LEN B", "LGF-A":"LGF A", "LGF-B":"LGF B", "MOG-A":"MOG A"}
#tickers = {"-":" "} # pro yahoo data, pokud nechceme vybirat konkretni tickery
#tickers = {"-":" "} # pro NorGate data , pokud nechceme vybirat konkretni tickery

# Cesta k BAT souboru, kterym startujeme TWS:
ibc = {
        'IBCPath' : 'C:\\_AOS_LIVE\\IBC_live\\StartTWS.bat'
}                                             