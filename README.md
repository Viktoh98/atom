# atom 
# DRF DOCUMENTATION

### LOGIN CREDENTIALS
username: victor
password: admin1234

### SETUP
AFter cloning the repo

-- Create Virtual environment
python -m venv venv

-- install requirements.txt
pip install -r requirements.txt

-- Run migrations
python manage.py makemigrations
python manage.py migrate

-- Start the server
python manage.py runserver



### WORKFLOW

The api consists of the base atom projects which holds all configurations and a single app named "api" which holds all our entire logic.

### api (app)
The api apps is made up of the following which are the core files for the api

-- storage.py
Helper functions which are used to load/read and write to the json files
    - load_json.py
    - save_json.py
    - logger.py

-- services.py 
Contains the functions which call the external api endpoints to search and fetch reviews.
 - search_company
 - fetch_reviews

 NOTE: It also holds the sensitiv data in form of the api key which should normally be stored in a .env file


-- views.py
These contains all logic for each of our url endpoints, the urls and the corresponding api views are mapped in the urls.py
    'auth/login', TokenObtainPairView, POST
    
    'companies/search', CompanySearchView, GET
    'companies/tracked', TrackCompanyListView, GET
        param required: 'query'
    'companies/track', TrackCompanyCreateView, POST
        required: {
            domain: string
        }
    'companies/untrack/<str:domain>', TrackCompanyDeleteView, DELETE
    'reviews/<str:domain>', ReviewView, GET


### BACKGROUND PROCESS (INCOMPLETE)
    The logic for the background process for fetching reviews of tracked domains is held in the "fetcher.py" which i would go into details later.

-- LIBRARY USED
    django-apscheduler

    NOTE: best Choice is usually Celery but redis is not supported directly on windows. Work around was time consuming and only other choice was to setup a redis server online which would take some time to test. Hence, the decidion to use  django-apscheduler

-- LOGIC:
    When reviews are fetched, they are usually sorted by date newest first but steps is also taken to sort newest first.
    the newest date is stored in the meta for the particular domain and. All reviews are fetched across all pages and stored in the json file initially.
    On the 5 minutes interval, the new reviews are fetched and the latest time is compared to that in the meta if it is the newer, the review is collected and added to the json file for the domain else it is logged that there was no new review in the jobs.json.