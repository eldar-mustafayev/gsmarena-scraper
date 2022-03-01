# from _typeshed import StrPath
import asyncio
from collections.abc import AsyncGenerator
import os
# 03:15
import yaml
from pathlib import Path
from typing import Iterator

import lxml.html
import aiohttp
from lxml.objectify import ObjectifiedElement
from proxy import Proxies
from user_agents import UserAgents

import ssl
import certifi
sslcontext = ssl.create_default_context(cafile=certifi.where())

BASE_URL = 'https://www.gsmarena.com/'


class TooManyRequests(aiohttp.ClientResponseError):
    "Client response to too many requests"

async def get_tree(session: aiohttp.ClientSession, url: str) -> ObjectifiedElement:
    timeout = aiohttp.ClientTimeout(10)
    loop = asyncio.get_event_loop()

    while True:

        try:
            connector = aiohttp.TCPConnector(ssl=False, loop=loop, force_close=True)
            async with aiohttp.request(
                "GET", url,
                headers=headers,
                proxy=proxy,
                #connector=connector,
                timeout=timeout
                ) as response:

                if response.status == 429:
                    raise TooManyRequests(
                        response.request_info,
                        response.history,
                        status=response.status,
                        message=response.reason,
                        headers=response.headers,
                    )
                    
                response.raise_for_status()

                content = await response.text()


            # async with aiohttp.ClientSession(headers=headers) as session:
            #     async with session.get(url, proxy=proxy, timeout=timeout, ssl=sslcontext) as response:
            #         if response.status == 429:
            #             raise aiohttp.ClientConnectionError
            #         response.raise_for_status()

            #         content = await response.text()

            return lxml.html.fromstring(content)

        except aiohttp.ClientHttpProxyError:
            print("Proxy error, choosing a new proxy")
            PROXIES.remove()
        except aiohttp.ClientProxyConnectionError:
            print("Proxy error, choosing a new proxy")
            PROXIES.remove()
        except aiohttp.ClientSSLError:
            print("SSL error, choosing a new proxy")
            PROXIES.remove()
        except asyncio.exceptions.TimeoutError:
            print("Timeout error, choosing a new proxy")
            PROXIES.remove()
        except TooManyRequests:
            print("Too many requests, choosing a new proxy")
            PROXIES.remove()
        except aiohttp.ClientConnectionError:
            print("Unknown connection error, choosing a new proxy")
            PROXIES.remove()
        except aiohttp.ClientResponseError:
            print("Unknown response error, trying again")
        except aiohttp.ClientError:
            print("Unknown error, trying again")


def get_phone_brands(tree: ObjectifiedElement) -> Iterator[tuple[str, str]]:
    brand_names = {
        'Apple',
        'BlackBerry',
        'Google',
        'Honor',
        'HTC',
        'Huawei',
        'LG',
        'Nokia',
        'Meizu',
        'OnePlus',
        'Oppo',
        'Realme',
        'Samsung',
        'Sony',
        'Xiaomi',
        'ZTE'
    }

    tree.make_links_absolute(BASE_URL)

    for brand_elem in tree.xpath('//td/a'):
        brand_name = brand_elem.text
        if brand_name not in brand_names:
            continue

        brand_url = brand_elem.get('href')
        yield brand_name, brand_url


async def get_brand_models(tree: ObjectifiedElement) -> AsyncGenerator[tuple[str, str], None]:

    async def get_pages(tree: ObjectifiedElement) -> AsyncGenerator[ObjectifiedElement, None]:
        tree.make_links_absolute(BASE_URL)
        page_urls = tree.xpath('//div[@class="nav-pages"]/a/@href')

        yield tree
        for url in page_urls:
            page = await get_tree(url)
            yield page

    def get_models_frompage(tree: ObjectifiedElement) -> Iterator[tuple[str, str]]:
        tree.make_links_absolute(BASE_URL)

        phone_names = tree.xpath('//div[@class="makers"]/ul/li/a/strong/span/text()')
        phone_urls = tree.xpath('//div[@class="makers"]/ul/li/a/@href')

        phone_names = map(str, phone_names)
        phone_urls = map(str, phone_urls)

        return zip(phone_names, phone_urls)

    async for page_tree in get_pages(tree):
        for model in get_models_frompage(page_tree):
            yield model


def fix_path(path: str) -> Path:
    return Path(__file__).parent.resolve() / Path(path)


def serialize(brand_name: str, model_name: str, model_tree: ObjectifiedElement) -> None:

    Path(f'./data/models/html/{brand_name}').mkdir(exist_ok=True)
    filepath = fix_path(f'./data/models/html/{brand_name}/{model_name}.html')

    with open(filepath, 'wb') as file:
        file.write(lxml.html.tostring(model_tree))

    print(f"Loaded {model_name}")


def get_scraped_data() -> dict[str, dict[str, list[str]]]:
    filepath = fix_path("./data/metadata/scraped.yml")
    with open(filepath, "r") as stream:
        scraped_data = yaml.load(stream, Loader=yaml.Loader)
        if scraped_data is None:
            scraped_data = {'brands': {}}

        return scraped_data


def set_scraped_data(scraped_data: dict[str, dict[str, list[str]]]):
    filepath = fix_path("./data/metadata/scraped.yml")
    with open(filepath, "w") as stream:
        yaml.dump(scraped_data, stream)


async def main():
    async with aiohttp.ClientSession() as session:
        scraped_models = get_scraped_data()

        main_tree = await get_tree(session, 'https://www.gsmarena.com/makers.php3')
        for brand_name, brand_url in get_phone_brands(main_tree):

            if brand_name not in scraped_models['brands']:
                scraped_models['brands'][brand_name] = []

            brand_tree = await get_tree(brand_url)
            async for model_name, model_url in get_brand_models(brand_tree):

                if model_name in scraped_models['brands'][brand_name]:
                    continue

                model_tree = await get_tree(model_url)
                serialize(brand_name, model_name, model_tree)

                scraped_models['brands'][brand_name].append(model_name)
                set_scraped_data(scraped_models)


if __name__ == '__main__':
    asyncio.run(main())
