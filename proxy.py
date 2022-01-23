import requests

from random import choice
from lxml.html import fromstring
from collections import deque


class Proxies:

    def __init__(self):
        self.proxy = None
        self.proxies = deque()

    def get_proxies(self):
        url = 'https://sslproxies.org'
        response = requests.get(url, verify=True)
        parser = fromstring(response.text)

        for i in parser.xpath('//tbody/tr'):
            if i.xpath('./td[5][contains(text(),"elite proxy")]'):
                if i.xpath('./td[7][contains(text(),"yes")]'):
                    ip = i.xpath('./td[1]/text()')[0]
                    port = i.xpath('./td[2]/text()')[0]
                    self.proxies.append(f'http://{ip}:{port}')


    @staticmethod
    def to_proxy(proxy):
        return {"http": proxy, "https": proxy}

    def get(self):
        if len(self.proxies) < 2:
            self.get_proxies()
        self.proxy = self.proxies[0]
        self.proxies.rotate(-1)
        return self.to_proxy(self.proxy)

    def remove(self):
        # Remove invalid proxy from pool
        self.proxies.popleft()
        self.proxy = self.get()

    def scrape(self, url, **kwargs):
        # Retry until request was sucessful
        while True:
            try:
                proxy = self.get()
                page = requests.get(url, proxies=proxy, **kwargs)
                print("Proxy currently being used: {}".format(proxy))
                return page

            # if the request is successful, no exception is raised
            except requests.exceptions.ProxyError:
                print("Proxy error, choosing a new proxy")
                self.remove()
            except requests.exceptions.Timeout:
                print("Timeout error, choosing a new proxy")
                self.remove()
            except requests.exceptions.SSLError:
                print("SSL error, choosing a new proxy")
            except requests.exceptions.ConnectionError:
                print("Connection error, choosing a new proxy")
                self.remove()

if __name__ == "__main__":
    proxy = Proxies()
    # Make each request using a randomly selected proxy
    r = proxy.scrape('https://httpbin.org/headers')
    print(r.text)