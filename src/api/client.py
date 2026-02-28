import os
from typing import Dict, Any, Optional

import requests
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

class HevyAPIClient:
    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key or os.getenv("HEVY_API_KEY")
        if not self.api_key:
            raise ValueError("HEVY_API_KEY is not set.")
        
        self.base_url = "https://api.hevyapp.com/v1"
        self.session = requests.Session()
        self.session.headers.update({
            "api-key": self.api_key,
            "Content-Type": "application/json"
        })

    def get(self, endpoint: str, parameters: Optional[Dict[str, Any]] = None) -> requests.Response:
        url = f"{self.base_url}/{endpoint}"
        response = self.session.get(url, params=parameters, timeout=15)
        response.raise_for_status()
        return response

    def put(self, endpoint: str, payload: BaseModel) -> requests.Response:
        url = f"{self.base_url}/{endpoint}"
        json_data = payload.model_dump(by_alias=True, exclude_none=True)
        response = self.session.put(url, json=json_data, timeout=15)
        response.raise_for_status()
        return response

    def post(self, endpoint: str, payload: BaseModel) -> requests.Response:
        url = f"{self.base_url}/{endpoint}"
        json_data = payload.model_dump(by_alias=True, exclude_none=True)
        response = self.session.post(url, json=json_data, timeout=15)
        response.raise_for_status()
        return response
