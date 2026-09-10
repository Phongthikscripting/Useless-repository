import aiohttp
import random
import string
from typing import Optional, List, Dict

class TempMail:
    DOMAINS = ["1secmail.com", "1secmail.org", "1secmail.net"]
    BASE_URL = "https://www.1secmail.com/api/v1/"
    
    def __init__(self):
        self.username = None
        self.domain = None
        self.email = None
    
    def generate(self) -> str:
        self.username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
        self.domain = random.choice(self.DOMAINS)
        self.email = f"{self.username}@{self.domain}"
        return self.email
    
    async def get_messages(self) -> List[Dict]:
        if not self.username or not self.domain:
            return []
        url = f"{self.BASE_URL}?action=getMessages&login={self.username}&domain={self.domain}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                return []
    
    async def read_message(self, message_id: str) -> Optional[Dict]:
        if not self.username or not self.domain:
            return None
        url = f"{self.BASE_URL}?action=readMessage&login={self.username}&domain={self.domain}&id={message_id}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                return None
