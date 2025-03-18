import requests

class api_harvest_info():
    def __init__(self, base_url="https://api.mangadex.org"):
        self.base_url = "https://api.mangadex.org"
        self.headers = {
                'User-Agent': 'MangaRecon/0.1 (Contact: tearedvpn@gmail.com : This is a student project, if I inconvenience you, it is not out of ill-will. Please let me know and Ill stop immediately.)'
            }
        
    def get_list_of_most_popular(self):
        params = {
        "order[rating]": "desc",
        "order[followedCount]": "desc"
        }

        try:
            response = requests.get(self.base_url, params=params)
            response.raise_for_status()

            manga_data = response.json()['data']

            manga_ids = []
            for manga in manga_data:
                manga_ids.append(manga['id'])
            return manga_ids
        
        except requests.exceptions.HTTPError as e:
            print(f"HTTP error occurred: {e}") 
        except requests.exceptions.RequestException as e:
            print(f"Error during requests to {self.base_url}: {e}") 
        except KeyError as e:
            print(f"Data parsing error - key not found: {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            return []


    def get_manga_details(self, manga_id):
        try:
            response = requests.get(f"{self.base_url}/manga/{manga_id}", headers=self.headers)
            response.raise_for_status()

            manga_details = response.json()['data']['attributes']
            relationships = response.json()['data']['relationships']

            authors = []
            for rel in relationships:
                if rel['type'] == 'author':
                    authors.append(rel['id'])

            tags = []
            for tag in manga_details['tags']:
                if 'en' in tag['attributes']['name']:
                    tags.append(tag['attributes']['name']['en'])

            details = {
                'title': manga_details['title'].get('en', 'No Title Available'),
                'description': manga_details['description'].get('en', 'No Description Available'),
                'authors': authors,
                'tags': tags
            }
            return details
        
        except requests.exceptions.HTTPError as e:
            print(f"HTTP error occurred for manga ID {manga_id}: {e}")
        except requests.exceptions.RequestException as e:
            print(f"Request exception for manga ID {manga_id}: {e}")
        except KeyError as e:
            print(f"Key error for manga ID {manga_id}: {e}")
        except Exception as e:
            print(f"Unexpected error for manga ID {manga_id}: {e}")
            return {}

    