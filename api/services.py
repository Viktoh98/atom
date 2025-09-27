import requests


#Store in .env in production
API_HOST = "trustpilot-company-and-reviews-data.p.rapidapi.com"
API_KEY =  "0f53fba71amshc1e707360665992p1b110ajsnc8e8801390d7"

HEADERS = {
    "x-rapidapi-host": API_HOST,
    "x-rapidapi-key": API_KEY,
}

def search_comapny(query):
    url = f"https://{API_HOST}/company-search?query={query}"
    result = requests.get(url=url, headers=HEADERS, timeout=10).json()
    return result


def fetch_reviews(domain):
    url = f"https://{API_HOST}/company-reviews?company_domain={domain}"
    result = requests.get(url=url, headers=HEADERS, timeout=10).json()
    return result