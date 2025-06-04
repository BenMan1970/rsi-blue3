import requests
import pandas as pd
import streamlit as st # Pour st.secrets et st.error/warning
import time

# @st.cache_data(ttl=300) # Cache pour 5 minutes
def get_data_alphavantage(from_symbol: str, to_symbol: str, interval: str = "60min", outputsize: str = "compact"):
    """
    Récupère les données OHLCV d'Alpha Vantage pour une paire Forex.
    from_symbol: e.g., 'EUR'
    to_symbol: e.g., 'USD'
    interval: '1min', '5min', '15min', '30min', '60min'
    outputsize: 'compact' (100 derniers points) ou 'full' (historique complet)
    """
    try:
        if 'alpha_vantage' not in st.secrets or 'API_KEY' not in st.secrets.get("alpha_vantage", {}):
            st.error("Clé API Alpha Vantage manquante dans les secrets Streamlit.")
            return None
        
        api_key = st.secrets["alpha_vantage"]["API_KEY"]
        
        # Pour 200 bougies H1, 'full' est plus sûr si 'compact' ne suffit pas.
        # Si 'compact' (100 points) est utilisé pour '60min', on aura que 100 heures.
        # Il faut souvent 'outputsize=full' pour avoir assez de données pour les indicateurs.
        # Le plan gratuit AV est limité, donc 'full' peut consommer plus de "requêtes effectives".
        # Pour un scan de 200 bougies H1, il faut 'outputsize=full' et ensuite on prend les dernières 200.
        
        # Ajustement de la logique outputsize:
        # Si on a besoin de 200 points et que 'compact' n'en donne que 100, il faut 'full'.
        # Cependant, l'API AV pour FX_INTRADAY ne retourne pas toujours un nombre fixe avec 'full'.
        # Il est plus simple de demander 'full' et de tronquer ensuite.
        current_outputsize = "full" # Pour avoir assez de données pour 200 bougies et calculs

        params = {
            "function": "FX_INTRADAY",
            "from_symbol": from_symbol,
            "to_symbol": to_symbol,
            "interval": interval,
            "outputsize": current_outputsize, 
            "apikey": api_key,
            "datatype": "json" # json est plus facile à parser que csv pour ce format
        }
        
        url = "https://www.alphavantage.co/query"
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status() # Lève une exception pour les codes d'erreur HTTP
        
        data = response.json()

        # Vérifier si la clé attendue est présente (varie selon l'endpoint et l'intervalle)
        time_series_key = f"Time Series FX ({interval})"
        if time_series_key not in data:
            error_message = data.get("Error Message") or data.get("Information") or data.get("Note")
            if error_message:
                st.warning(f"AlphaVantage pour {from_symbol}{to_symbol}: {error_message}")
            else:
                st.warning(f"Données AlphaVantage non trouvées pour {from_symbol}{to_symbol} avec la clé '{time_series_key}'. Réponse: {data}")
            return None

        time_series = data[time_series_key]
        df = pd.DataFrame.from_dict(time_series, orient='index')
        
        if df.empty:
            st.warning(f"Aucune donnée dans la série temporelle AlphaVantage pour {from_symbol}{to_symbol}")
            return None

        # Renommer les colonnes et convertir en numérique
        df.rename(columns={
            '1. open': 'Open',
            '2. high': 'High',
            '3. low': 'Low',
            '4. close': 'Close'
        }, inplace=True)
        
        for col in ['Open', 'High', 'Low', 'Close']:
            df[col] = pd.to_numeric(df[col])
        
        # L'index est une string, le convertir en datetime et trier
        df.index = pd.to_datetime(df.index)
        df.sort_index(ascending=True, inplace=True) # Très important, AV les donne en ordre inversé

        required_candles = 200 # Ou la variable 'count'
        if len(df) < 60: # Seuil minimal pour les calculs
            st.warning(f"Données AlphaVantage insuffisantes pour {from_symbol}{to_symbol} ({len(df)} bougies). Min 60.")
            return None
        
        return df[['Open', 'High', 'Low', 'Close']].tail(required_candles)

    except requests.exceptions.HTTPError as http_err:
        st.error(f"Erreur HTTP AlphaVantage pour {from_symbol}{to_symbol}: {http_err} - Réponse: {response.text}")
        return None
    except requests.exceptions.RequestException as req_err:
        st.error(f"Erreur de requête AlphaVantage pour {from_symbol}{to_symbol}: {req_err}")
        return None
    except Exception as e:
        st.error(f"Erreur inattendue avec AlphaVantage pour {from_symbol}{to_symbol}: {str(e)}")
        # import traceback
        # st.error(traceback.format_exc())
        return None

# PAIRS_ALPHA_VANTAGE devrait être une liste de tuples ou de dicts, ex:
# [{'from': 'EUR', 'to': 'USD'}, {'from': 'GBP', 'to': 'USD'}, ...]
#
# Dans la boucle de scan:
# for pair_info in PAIRS_ALPHA_VANTAGE:
#     data_h1_av = get_data_alphavantage(pair_info['from'], pair_info['to'], interval="60min")
#     # N'oubliez pas la limite de 5 req/min pour le plan gratuit Alpha Vantage !
#     time.sleep(15) # Attendre 15 secondes entre les appels pour respecter la limite gratuite
