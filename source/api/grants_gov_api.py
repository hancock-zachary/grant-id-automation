"""
Grants.gov API Client
"""
#%% Import modules and libraries
# First-party libraries
from datetime import datetime, timedelta
import json
import time

# Third-party libraries
from dataclasses import dataclass, asdict
import logging
import requests
from tqdm import tqdm
from typing import Dict, List, Optional, Any

# Custom modules


#%% API error exception class.
class APIError(Exception):
    """Base exception for FAC API errors"""
    pass


#%%
class GrantsGovAPIClient:
    """
    Client for interacting with Grants.gov RESTful API
    """
    def __init__(self):
        """
        Initialize the API client
        """
        # URLs
        self.base_url = "https://api.grants.gov/v1/api"
        self.endpoints = {
            "search 2" : "/search2"
            , "fetch opportunity" : "/fetchOpportunity"
        }

        # Set up session to access API
        self.session = requests.Session()
        # self.session.headers.update({})
    

    # Base functions.
    def _validate_string(self, input_string: str) -> str:
        """
        Purpose:
            Validate and normalize string inputs. Strings are normalized to be lower case and to be stripped of extra spaces.
        Args:
            input_string: String to validate.
        Returns:
            Normalized string value.
        Raises:
            ValueError: If string is None or invalid.
            TypeError: If string is not a string.
        """
        if input_string is None:
            raise ValueError("input_string cannot be None.")
        
        if not isinstance(input_string, str):
            raise TypeError(f"input_string must be str, got {type(input_string).__name__}.")
        
        output_string = input_string.strip().lower()  # Normalize the string variable.
        return output_string
    
    def _make_request(self
                      , endpoint_name: str
                      , params: Dict = None
                      , handle_429: bool = False
                      ) -> List[Dict]:
        """
        Purpose:
            Make an endpoint specific API request with error handling.
        Args:
            endpoint_name: Name of the endpoint (e.g., 'general', 'findings')
            params: Query parameters to include in the request
            handle_429: If True, automatically retry on 429 errors indefinitely using Retry-After header
        Returns:
            List of records from the API.
        Raises:
            APIError: If the API request fails
            ValueError: If endpoint_name is invalid
            TypeError: If endpoint_name is not a string
        """
        # Exception and type handling for endpoint_name variable.
        endpoint_name = self._validate_string(endpoint_name)
        if endpoint_name not in self.endpoints:
            available = ', '.join(self.endpoints.keys())
            raise ValueError(f"Unknown endpoint: '{endpoint_name}'. Available: {available}")
        
        endpoint = self.endpoints.get(f"{endpoint_name}")  # Identify the endpoint to add to the url.
        url = f"{self.base_url}{endpoint}"  # Add endpoint to the base url.
        
        while True:
            try:
                response = self.session.get(url, params=params or {})
                response.raise_for_status()  # Raises exception for bad status codes.
                result = response.json()

                if isinstance(result, list):  # FAC API returns data as a list
                    return result
                else:
                    # print(f"Warning: Expected list from {endpoint_name}, got {type(result)}")  # Log unexpected response format
                    tqdm.write(f"Warning: Expected list from {endpoint_name}, got {type(result)}")  # Log unexpected response format
                    return []
            except requests.exceptions.HTTPError as e:
                if response.status_code == 401:
                    raise APIError("Authentication failed. Check your API key.") from e
                elif response.status_code == 404:
                    raise APIError(f"Endpoint not found: {endpoint_name}") from e
                elif response.status_code == 429:
                    if not handle_429:
                        raise APIError("Rate limit exceeded. Please wait before making more requests.") from e
                    else:
                        retry_after = response.headers.get('Retry-After') or response.headers.get('retry-after')
                        if retry_after:
                            try:
                                wait_time = float(retry_after)
                                
                                tqdm.write(f"Rate limit hit. Server requested {retry_after}s wait. Waiting {(wait_time ** 2):.1f}s...")
                                wait_time *= 2  # Double the wait time to be safe.
                                time.sleep(wait_time)
                                continue
                            except ValueError:
                                print(f"Invalid Retry-After header: {retry_after}")
                else:
                    raise APIError(f"HTTP {response.status_code} error for {endpoint_name}: {e}") from e
            except requests.exceptions.ConnectionError as e:
                raise APIError(f"Failed to connect to FAC API: {e}") from e
            except requests.exceptions.Timeout as e:
                raise APIError(f"Request timeout for {endpoint_name}: {e}") from e
            except requests.exceptions.RequestException as e:
                raise APIError(f"Request failed for {endpoint_name}: {e}") from e
            except ValueError as e:  # JSON decode error
                raise APIError(f"Invalid JSON response from {endpoint_name}: {e}") from e
    

    # Search2 Endpoint
    def search2_get_request(self):
        return self._make_request(endpoint_name='search 2', params={}, handle_429=True)
    

    # FetchOpportunity Endpoint
    def fetchOpportunity_get_request(self):
        return self._make_request(endpoint_name='fetch opportunity', params={}, handle_429=True)


#%% Example usage
if __name__ == "__main__":
    pass


#%% End of code.