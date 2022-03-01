import requests
from lxml.html import fromstring
from collections import deque


class Proxies:

    def __init__(self):
        self.proxies = deque()

    def refresh_proxies(self) -> None:
        url = 'https://sslproxies.org'
        response = requests.get(url, verify=True)
        parser = fromstring(response.text)

        for i in parser.xpath('//tbody/tr'):
            if i.xpath('./td[5][contains(text(),"elite proxy")]'):
                if i.xpath('./td[7][contains(text(),"yes")]'):
                    ip = i.xpath('./td[1]/text()')[0]
                    port = i.xpath('./td[2]/text()')[0]
                    self.proxies.append(f'http://{ip}:{port}')

    def get(self) -> str:
        if len(self.proxies) < 2:
            self.refresh_proxies()

        proxy = self.proxies[0]
        self.proxies.rotate(-1)

        print(f"Proxy currently being used: {proxy}")
        return proxy

    def remove(self):
        self.proxies.popleft()
