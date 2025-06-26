# config.py

# OpenAI API key
OPENAI_API_KEY = 'xxx' # Remember to replace this with your actual key!

# Interactive Brokers connection details
# These are used for ib_insync.IB().connect() directly
IB_HOST = '127.0.0.1'
IB_PORT = 7497

# Path to the database
DATABASE_PATH = 'data/IBFlexQuery.db'

# Email parameters
# SendMail - False / True - determines if the system sends emails
# SmtpServer, FromAddress, Password - server settings and outgoing mail authorization
# ToAddress - target email - ['first@example.com', 'second@example.com']
EMAIL_SETTINGS = {
    'SendMail' : True,
    'FromAddress' : 'tomasxxxxx@seznam.cz',
    'Password' : 'xxxxx@-BQ', # new password for SMTP and mail clients
    'ToAddress' : 'tomas.xxxxx@gmail.com',
    # 'ToAddress' : ['tomas.xxxxx@gmail.com', 'xxxxx@email.cz'],
    'SmtpServer' : 'smtp.seznam.cz',
    'Port' : 587
}

# System log file name
LOG_FILE_SETTINGS = {
    'filename' : 'autotrader.log'
}
NEWS_API_KEY = ''
# Token
TOKEN = 'xxx'

# Query ID for Flex Query
QUERY_ID = 'xxx'
# QUERY_ID = '877428' # for Year To Date data

# Exchange rate for capital conversion, used in case of error loading CZK/USD rate from IB
STATIC_EXCHANGE_RATE = 22.62

# Path where AmiBroker saves project files
# e.g., 'c:/Programy/AmiBroker/Projekty/'
AMIBROKER_SETTINGS = {
    'ProjectPath' : 'c:/Program Files/AmiBroker/Formulas/Custom/AnalysisProjectsAndBatch/'
}

# Modification inspired by user with nickname Ichram
# Ticker name adjustment for IB
TICKER_MAPPING = {
    "BF-A":"BF A", "BF-B":"BF B", "BRK-B":"BRK B", "CRD-A":"CRD A",
    "CWEN-A":"CWEN A", "GEF-B":"GEF B", "HEI-A": "HEI A", "JW-A":"JW A",
    "LEN-B":"LEN B", "LGF-A":"LGF A", "LGF-B":"LGF B", "MOG-A":"MOG A"
}
# TICKER_MAPPING = {"-":" "} # for yahoo data, if we don't want to select specific tickers
# TICKER_MAPPING = {"-":" "} # for NorGate data, if we don't want to select specific tickers

# Path to the BAT file to start TWS:
# IBCPath: 'C:\\_AOS_LIVE\\IBC_live\\StartTWS.bat' in the ProjectFolder/config folder
IBC_SETTINGS = {
    'IBCPath' : 'C:\\_AOS_LIVE\\IBC_live\\StartTWS.bat'
}
